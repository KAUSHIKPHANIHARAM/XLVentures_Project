"""
memory/__init__.py

Public API for the memory module.

Usage:
    from memory import get_memory_store, AbstractMemoryStore
    from memory import ChromaDBMemoryStore
    from memory import EpisodicMemory
    from memory import MemoryStoreError
"""

from memory.base import (
    AbstractMemoryStore,
    MemoryStoreConnectionError,
    MemoryStoreError,
    MemoryStoreWriteError,
)
from memory.chromadb_store import ChromaDBMemoryStore
from memory.embeddings import get_embedding_function
from memory.episodic import EpisodicMemory
from memory.store_registry import get_memory_store, reset_memory_store

__all__ = [
    # Interface
    "AbstractMemoryStore",
    # Exceptions
    "MemoryStoreError",
    "MemoryStoreConnectionError",
    "MemoryStoreWriteError",
    # Implementations
    "ChromaDBMemoryStore",
    # Registry
    "get_memory_store",
    "reset_memory_store",
    # Services
    "EpisodicMemory",
    # Utilities
    "get_embedding_function",
]
