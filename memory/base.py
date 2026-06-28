"""
memory/base.py

AbstractMemoryStore — the vector memory interface for the platform.

All modules that need to store or retrieve memories (agents, knowledge
ingestion, episodic recorder) depend on this interface only.
The ChromaDB implementation can be swapped for any other vector store
(Pinecone, Weaviate, FAISS) without changing any consumer code.

Design:
    - Domain-scoped: each method takes 'domain' so one store can serve
      multiple domains (just different collections).
    - memory_type distinguishes EPISODIC vs SEMANTIC retrieval.
    - Batch operations are provided for efficient bulk inserts (knowledge ingestion).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from schemas.memory import MemoryEntry, MemoryType, RetrievalResult


class AbstractMemoryStore(ABC):
    """
    Abstract interface for vector memory storage and retrieval.

    Concrete implementations: ChromaDBMemoryStore (default).
    Future: PineconeMemoryStore, FAISSMemoryStore, etc.
    """

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @abstractmethod
    def store(self, entry: MemoryEntry) -> str:
        """
        Store a single memory entry.

        Args:
            entry: The MemoryEntry to embed and store.

        Returns:
            The entry_id of the stored entry.
        """

    @abstractmethod
    def store_batch(self, entries: list[MemoryEntry]) -> list[str]:
        """
        Store multiple memory entries in a single batch operation.

        More efficient than calling store() repeatedly for large ingestions.

        Args:
            entries: List of MemoryEntry objects to store.

        Returns:
            List of entry_ids in the same order as the input.
        """

    @abstractmethod
    def delete(self, entry_id: str, domain: str, memory_type: MemoryType) -> bool:
        """
        Delete a single memory entry by ID.

        Args:
            entry_id:    ID of the entry to delete.
            domain:      Domain the entry belongs to.
            memory_type: Type of memory (to locate the correct collection).

        Returns:
            True if deleted, False if not found.
        """

    @abstractmethod
    def delete_by_domain(self, domain: str, memory_type: MemoryType) -> int:
        """
        Delete all memory entries for a domain and type.

        Useful for re-ingesting knowledge without duplicates.

        Args:
            domain:      Domain to clear.
            memory_type: Memory type to clear.

        Returns:
            Number of entries deleted.
        """

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @abstractmethod
    def retrieve(
        self,
        query: str,
        domain: str,
        memory_type: MemoryType,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        """
        Retrieve the most semantically similar entries for a query.

        Args:
            query:       Natural language query text to embed and search.
            domain:      Domain to search within.
            memory_type: EPISODIC or SEMANTIC.
            top_k:       Maximum number of results to return.
            filters:     Optional metadata filters (exact match on stored metadata).

        Returns:
            RetrievalResult with ranked results by similarity.
        """

    @abstractmethod
    def count(self, domain: str, memory_type: MemoryType) -> int:
        """
        Return the number of entries in a domain/type collection.

        Args:
            domain:      Domain to count.
            memory_type: Memory type to count.

        Returns:
            Integer count of stored entries.
        """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the vector store is reachable and functional."""


class MemoryStoreError(Exception):
    """Base exception for memory store errors."""


class MemoryStoreConnectionError(MemoryStoreError):
    """Raised when the vector store cannot be reached."""


class MemoryStoreWriteError(MemoryStoreError):
    """Raised when a write operation fails."""
