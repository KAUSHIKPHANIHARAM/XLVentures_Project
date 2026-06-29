"""
memory/chromadb_store.py

ChromaDBMemoryStore — ChromaDB implementation of AbstractMemoryStore.

Uses one ChromaDB collection per (domain, memory_type) pair.
Collection names follow the pattern: {prefix}_{domain}_{memory_type}
Example: adip_customer_management_semantic

Design:
    - PersistentClient: data survives restarts (written to disk).
    - get_or_create_collection: idempotent — safe to call on every startup.
    - Metadata filtering uses ChromaDB's `where` clause syntax.
    - Similarity scores are converted from ChromaDB's distance metric
      (cosine distance [0,2]) to similarity score [0,1].
    - Batch inserts chunk large lists into safe sizes (ChromaDB limit).
"""

from __future__ import annotations

import logging
from typing import Any

from config.schemas import EmbeddingConfig, VectorDBConfig
from memory.base import (
    AbstractMemoryStore,
    MemoryStoreConnectionError,
    MemoryStoreWriteError,
)
from memory.embeddings import get_embedding_function
from schemas.memory import MemoryEntry, MemoryType, RetrievalResult, RetrievedMemory
from utils.logging import get_logger

logger = get_logger(__name__)

# ChromaDB's max batch size for add operations
_CHROMA_BATCH_SIZE = 100


class ChromaDBMemoryStore(AbstractMemoryStore):
    """
    ChromaDB vector store implementation.

    Args:
        vector_config:    VectorDBConfig (persist_directory, collection_prefix).
        embedding_config: EmbeddingConfig (provider, model, api_key_env).
    """

    def __init__(
        self,
        vector_config: VectorDBConfig,
        embedding_config: EmbeddingConfig,
    ) -> None:
        self._config = vector_config
        self._embedding_config = embedding_config
        self._client = self._init_client()
        self._embedding_fn = get_embedding_function(embedding_config)
        self._collection_cache: dict[str, Any] = {}
        logger.info(
            "ChromaDBMemoryStore initialized. Persist directory: '%s'.",
            vector_config.persist_directory,
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def store(self, entry: MemoryEntry) -> str:
        """Embed and store a single MemoryEntry."""
        collection = self._get_collection(entry.domain, entry.memory_type)
        try:
            collection.upsert(
                ids=[entry.entry_id],
                documents=[entry.content],
                metadatas=[entry.to_chroma_metadata()],
            )
            logger.debug(
                "Stored memory entry '%s' in domain='%s' type='%s'.",
                entry.entry_id,
                entry.domain,
                entry.memory_type.value,
            )
            return entry.entry_id
        except Exception as exc:
            raise MemoryStoreWriteError(
                f"Failed to store memory entry '{entry.entry_id}': {exc}"
            ) from exc

    def store_batch(self, entries: list[MemoryEntry]) -> list[str]:
        """Store multiple MemoryEntries in batches for efficiency."""
        if not entries:
            return []

        stored_ids: list[str] = []

        # Group by (domain, memory_type) to minimise collection lookups
        groups: dict[tuple[str, MemoryType], list[MemoryEntry]] = {}
        for entry in entries:
            key = (entry.domain, entry.memory_type)
            groups.setdefault(key, []).append(entry)

        for (domain, memory_type), group_entries in groups.items():
            collection = self._get_collection(domain, memory_type)
            ids = _batch_upsert(collection, group_entries)
            stored_ids.extend(ids)
            logger.info(
                "Batch stored %d entries in domain='%s' type='%s'.",
                len(ids),
                domain,
                memory_type.value,
            )

        return stored_ids

    def delete(
        self, entry_id: str, domain: str, memory_type: MemoryType
    ) -> bool:
        collection = self._get_collection(domain, memory_type)
        try:
            collection.delete(ids=[entry_id])
            return True
        except Exception as exc:
            logger.warning("Failed to delete entry '%s': %s", entry_id, exc)
            return False

    def delete_by_domain(self, domain: str, memory_type: MemoryType) -> int:
        """Delete all entries in a domain/type collection (full clear)."""
        collection = self._get_collection(domain, memory_type)
        try:
            # ChromaDB: get all IDs then delete
            existing = collection.get(include=[])
            ids = existing.get("ids", [])
            if ids:
                collection.delete(ids=ids)
            logger.info(
                "Deleted %d entries from domain='%s' type='%s'.",
                len(ids), domain, memory_type.value,
            )
            return len(ids)
        except Exception as exc:
            logger.error("Failed to clear collection: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        domain: str,
        memory_type: MemoryType,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        """Semantic similarity search against a domain/type collection."""
        collection = self._get_collection(domain, memory_type)

        try:
            # Build ChromaDB where clause from filters
            where = _build_where_clause(filters) if filters else None

            kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": min(top_k, max(1, self.count(domain, memory_type))),
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            results = collection.query(**kwargs)

        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return RetrievalResult(
                query=query, domain=domain, memory_type=memory_type, results=[], total_found=0
            )

        retrieved = _parse_query_results(results, domain, memory_type)

        logger.debug(
            "Retrieved %d results for query='%.50s' domain='%s' type='%s'.",
            len(retrieved), query, domain, memory_type.value,
        )

        return RetrievalResult(
            query=query,
            domain=domain,
            memory_type=memory_type,
            results=retrieved,
            total_found=len(retrieved),
        )

    def count(self, domain: str, memory_type: MemoryType) -> int:
        """Return the number of entries in a collection."""
        try:
            collection = self._get_collection(domain, memory_type)
            return collection.count()
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify ChromaDB is reachable."""
        try:
            self._client.heartbeat()
            return True
        except Exception as exc:
            logger.error("ChromaDB health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_client(self) -> Any:
        """Create the ChromaDB persistent client."""
        try:
            import chromadb  # type: ignore[import-untyped]
            from pathlib import Path

            persist_path = self._config.persist_directory
            Path(persist_path).mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=persist_path)
            logger.info("ChromaDB PersistentClient created at '%s'.", persist_path)
            return client
        except ImportError as exc:
            raise MemoryStoreConnectionError(
                "chromadb package is not installed. "
                "Run: pip install chromadb"
            ) from exc

    def _get_collection(self, domain: str, memory_type: MemoryType) -> Any:
        """Get or create a ChromaDB collection for a domain/type pair."""
        collection_name = self._collection_name(domain, memory_type)

        if collection_name not in self._collection_cache:
            try:
                # Use the configured embedding function (e.g., OpenAI) to avoid fallback downloads.
                collection = self._client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=self._embedding_fn,
                    metadata={"hnsw:space": self._config.distance_metric},
                )
            except ValueError as exc:
                # If there's an embedding function conflict (e.g. key changed from default to openai),
                # recreate the collection automatically.
                if "embedding function" in str(exc).lower() or "conflict" in str(exc).lower():
                    logger.warning(
                        "Embedding function conflict in collection '%s'. Resetting collection...",
                        collection_name,
                    )
                    try:
                        self._client.delete_collection(collection_name)
                    except Exception:
                        pass
                    collection = self._client.get_or_create_collection(
                        name=collection_name,
                        embedding_function=self._embedding_fn,
                        metadata={"hnsw:space": self._config.distance_metric},
                    )
                else:
                    raise

            self._collection_cache[collection_name] = collection
            logger.debug("Collection '%s' ready.", collection_name)

        return self._collection_cache[collection_name]

    def _collection_name(self, domain: str, memory_type: MemoryType) -> str:
        """Generate the collection name for a domain/type pair."""
        prefix = self._config.collection_prefix
        # ChromaDB collection names: lowercase, no spaces, 3-63 chars
        safe_domain = domain.lower().replace(" ", "_").replace("-", "_")
        return f"{prefix}_{safe_domain}_{memory_type.value}"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _batch_upsert(collection: Any, entries: list[MemoryEntry]) -> list[str]:
    """Upsert entries in safe-sized batches. Returns list of stored IDs."""
    stored_ids: list[str] = []
    for i in range(0, len(entries), _CHROMA_BATCH_SIZE):
        batch = entries[i : i + _CHROMA_BATCH_SIZE]
        ids = [e.entry_id for e in batch]
        docs = [e.content for e in batch]
        metas = [e.to_chroma_metadata() for e in batch]
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        stored_ids.extend(ids)
    return stored_ids


def _parse_query_results(
    results: dict[str, Any],
    domain: str,
    memory_type: MemoryType,
) -> list[RetrievedMemory]:
    """Parse ChromaDB query result dict into RetrievedMemory list."""
    retrieved: list[RetrievedMemory] = []

    ids_list = results.get("ids", [[]])[0]
    docs_list = results.get("documents", [[]])[0]
    metas_list = results.get("metadatas", [[]])[0]
    distances_list = results.get("distances", [[]])[0]

    for entry_id, doc, meta, dist in zip(ids_list, docs_list, metas_list, distances_list):
        # Convert cosine distance [0,2] → similarity [0,1]
        # For cosine: distance = 1 - similarity → similarity = 1 - distance
        similarity = max(0.0, min(1.0, 1.0 - float(dist)))

        tags_raw = meta.get("tags", "")
        tags = [t for t in tags_raw.split(",") if t] if tags_raw else []

        entry_memory_type_val = meta.get("memory_type", memory_type.value)
        try:
            entry_memory_type = MemoryType(entry_memory_type_val)
        except ValueError:
            entry_memory_type = memory_type

        retrieved.append(
            RetrievedMemory(
                entry_id=entry_id,
                content=doc,
                similarity_score=similarity,
                memory_type=entry_memory_type,
                domain=meta.get("domain", domain),
                entity_type=meta.get("entity_type") or None,
                entity_id=meta.get("entity_id") or None,
                tags=tags,
                metadata={k: v for k, v in meta.items() if k not in ("tags",)},
                created_at=meta.get("created_at", ""),
            )
        )

    # Sort by similarity descending
    retrieved.sort(key=lambda r: r.similarity_score, reverse=True)
    return retrieved


def _build_where_clause(filters: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convert a simple filters dict to a ChromaDB `where` clause.

    ChromaDB where syntax: {"field": {"$eq": value}} for single conditions,
    or {"$and": [...]} for multiple.
    """
    if not filters:
        return None

    conditions = [
        {key: {"$eq": str(value)}}
        for key, value in filters.items()
        if value is not None
    ]

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}
