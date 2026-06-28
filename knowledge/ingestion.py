"""
knowledge/ingestion.py

KnowledgeIngestionService — chunks and embeds domain knowledge into ChromaDB.

Reads KnowledgeSourceConfig objects from the domain YAML, splits content
into overlapping chunks, converts to MemoryEntry objects, and stores them
in the semantic memory collection via the memory store.

Design:
    - Idempotent: clears and re-ingests if force=True; skips if data exists.
    - Works with any knowledge source type: 'inline' (text in YAML),
      'file' (read from disk), or extensible to 'url'.
    - Uses utils.text.chunk_text for paragraph-aware chunking.
    - One collection per domain keeps knowledge isolated between domains.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from config.schemas import DomainConfig, KnowledgeSourceConfig
from memory.base import AbstractMemoryStore
from schemas.memory import KnowledgeChunk, MemoryType
from utils.logging import get_logger
from utils.text import chunk_text, sanitize_string

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class KnowledgeIngestionService:
    """
    Ingests domain knowledge sources into the semantic memory store.

    Args:
        store:         The AbstractMemoryStore (ChromaDB semantic collection).
        domain_config: Domain configuration containing knowledge_sources.
    """

    def __init__(
        self, store: AbstractMemoryStore, domain_config: DomainConfig
    ) -> None:
        self._store = store
        self._domain = domain_config.name
        self._domain_config = domain_config

    def ingest_all(self, force: bool = False) -> dict[str, int]:
        """
        Ingest all knowledge sources defined in the domain config.

        Args:
            force: If True, clears existing knowledge and re-ingests.
                   If False, skips if knowledge already exists (idempotent).

        Returns:
            Dict of source_name → number of chunks stored.
        """
        sources = self._domain_config.knowledge_sources
        if not sources:
            logger.info(
                "No knowledge sources defined for domain '%s'. Skipping.",
                self._domain,
            )
            return {}

        # Idempotency check
        if not force:
            existing_count = self._store.count(self._domain, MemoryType.SEMANTIC)
            if existing_count > 0:
                logger.info(
                    "Domain '%s' already has %d semantic memory entries — "
                    "skipping ingestion (use force=True to re-ingest).",
                    self._domain,
                    existing_count,
                )
                return {}

        # Full clear before re-ingesting (avoids duplicates)
        cleared = self._store.delete_by_domain(self._domain, MemoryType.SEMANTIC)
        if cleared > 0:
            logger.info("Cleared %d existing entries before re-ingestion.", cleared)

        results: dict[str, int] = {}
        for source in sources:
            if not source.name:
                continue
            chunks_stored = self._ingest_source(source)
            results[source.name] = chunks_stored

        total = sum(results.values())
        logger.info(
            "Knowledge ingestion complete for domain '%s': "
            "%d total chunks across %d source(s). Breakdown: %s",
            self._domain,
            total,
            len(results),
            results,
        )
        return results

    def _ingest_source(self, source: KnowledgeSourceConfig) -> int:
        """Ingest a single knowledge source. Returns chunks stored."""
        logger.debug("Ingesting knowledge source: '%s' (type=%s)", source.name, source.type)

        content = self._load_content(source)
        if not content or not content.strip():
            logger.warning("Knowledge source '%s' has empty content — skipping.", source.name)
            return 0

        content = sanitize_string(content)

        # Chunk the content
        raw_chunks = chunk_text(
            content,
            chunk_size=source.chunk_size,
            chunk_overlap=source.chunk_overlap,
        )

        if not raw_chunks:
            logger.warning("Knowledge source '%s' produced no chunks.", source.name)
            return 0

        # Build KnowledgeChunk objects → MemoryEntry objects
        total_chunks = len(raw_chunks)
        entries = []
        for i, chunk_text_content in enumerate(raw_chunks):
            chunk = KnowledgeChunk(
                source_name=source.name,
                domain=self._domain,
                content=chunk_text_content,
                chunk_index=i,
                total_chunks=total_chunks,
                tags=list(source.tags),
            )
            entries.append(chunk.to_memory_entry())

        # Batch store all chunks
        stored_ids = self._store.store_batch(entries)

        logger.info(
            "Source '%s': %d chunk(s) stored.",
            source.name,
            len(stored_ids),
        )
        return len(stored_ids)

    def _load_content(self, source: KnowledgeSourceConfig) -> str:
        """Load raw text content based on source type."""
        if source.type == "inline":
            return source.content or ""

        if source.type == "file":
            if not source.path:
                logger.warning(
                    "Knowledge source '%s' is type='file' but has no path.", source.name
                )
                return ""
            file_path = Path(source.path)
            if not file_path.exists():
                logger.warning(
                    "Knowledge source '%s' file not found: '%s'.", source.name, file_path
                )
                return ""
            return file_path.read_text(encoding="utf-8")

        # 'url' type is a future extension point
        logger.warning(
            "Unsupported knowledge source type '%s' for source '%s'. "
            "Supported types: ['inline', 'file'].",
            source.type,
            source.name,
        )
        return ""
