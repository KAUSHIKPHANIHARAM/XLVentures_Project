"""
memory/store_registry.py

Global registry for the memory store singleton.

The memory store is expensive to initialise (it connects to ChromaDB and
loads embedding models). This module ensures it is created once and
reused across all consumers — agents, knowledge ingestion, episodic recorder.

Design:
    - Thread-safe lazy initialisation.
    - Factory-driven: the store type is determined by VectorDBConfig.provider.
    - reset() for test isolation.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from memory.base import AbstractMemoryStore

if TYPE_CHECKING:
    from config.schemas import EmbeddingConfig, VectorDBConfig

logger = logging.getLogger(__name__)

_store: AbstractMemoryStore | None = None
_lock = threading.Lock()


def get_memory_store(
    vector_config: "VectorDBConfig | None" = None,
    embedding_config: "EmbeddingConfig | None" = None,
) -> AbstractMemoryStore:
    """
    Return the singleton memory store, initialising it on first call.

    Args:
        vector_config:    Required on first call. Ignored on subsequent calls.
        embedding_config: Required on first call. Ignored on subsequent calls.

    Returns:
        The initialized AbstractMemoryStore.

    Raises:
        RuntimeError: If called without config on first call.
    """
    global _store  # noqa: PLW0603

    with _lock:
        if _store is not None:
            return _store

        if vector_config is None or embedding_config is None:
            raise RuntimeError(
                "Memory store has not been initialized. "
                "Call get_memory_store(vector_config, embedding_config) "
                "at application startup."
            )

        _store = _create_store(vector_config, embedding_config)
        logger.info(
            "Memory store initialized. Provider='%s'.", vector_config.provider
        )
        return _store


def reset_memory_store() -> None:
    """Clear the cached store (for tests only)."""
    global _store  # noqa: PLW0603
    with _lock:
        _store = None
    logger.debug("Memory store reset.")


def _create_store(
    vector_config: "VectorDBConfig",
    embedding_config: "EmbeddingConfig",
) -> AbstractMemoryStore:
    """Instantiate the correct store based on vector_config.provider."""
    provider = vector_config.provider.lower()

    if provider == "chromadb":
        from memory.chromadb_store import ChromaDBMemoryStore
        return ChromaDBMemoryStore(vector_config, embedding_config)

    # Extensibility point — add future providers here:
    # if provider == "pinecone":
    #     from memory.pinecone_store import PineconeMemoryStore
    #     return PineconeMemoryStore(vector_config, embedding_config)

    raise ValueError(
        f"Unsupported vector store provider '{provider}'. "
        f"Supported: ['chromadb']."
    )
