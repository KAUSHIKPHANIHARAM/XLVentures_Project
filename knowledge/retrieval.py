"""
knowledge/retrieval.py

KnowledgeRetrievalService — semantic search over the domain knowledge base.

This is what the knowledge_agent and decision_agent call at runtime to
surface relevant policies, playbooks, and guidelines for a user query.

Design:
    - Thin wrapper over the semantic memory retrieve() method.
    - Returns plain text strings (not MemoryEntry objects) for easy
      injection into agent prompts.
    - Formats retrieved chunks into a context block with source attribution.
"""

from __future__ import annotations

import logging
from typing import Any

from memory.base import AbstractMemoryStore
from schemas.memory import MemoryType, RetrievalResult
from utils.logging import get_logger

logger = get_logger(__name__)


class KnowledgeRetrievalService:
    """
    Retrieves relevant knowledge chunks from the semantic memory store.

    Args:
        store:  The AbstractMemoryStore.
        domain: Domain to retrieve knowledge from.
        top_k:  Default number of results per query (overridable per call).
    """

    def __init__(
        self,
        store: AbstractMemoryStore,
        domain: str,
        top_k: int = 5,
    ) -> None:
        self._store = store
        self._domain = domain
        self._default_top_k = top_k

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        tags: list[str] | None = None,
    ) -> RetrievalResult:
        """
        Retrieve the most relevant knowledge chunks for a query.

        Args:
            query:  Natural language query.
            top_k:  Number of results (defaults to the service's top_k).
            tags:   Optional tag filter (e.g. ['policy'] for policy-only retrieval).

        Returns:
            RetrievalResult with ranked knowledge chunks.
        """
        k = top_k or self._default_top_k
        filters: dict[str, Any] | None = None

        result = self._store.retrieve(
            query=query,
            domain=self._domain,
            memory_type=MemoryType.SEMANTIC,
            top_k=k,
            filters=filters,
        )

        logger.debug(
            "Knowledge retrieval: query='%.50s' found=%d chunks.",
            query,
            result.total_found,
        )
        return result

    def retrieve_as_context(
        self,
        query: str,
        top_k: int | None = None,
        min_similarity: float = 0.3,
    ) -> str:
        """
        Retrieve knowledge and format it as a prompt context block.

        Returns a formatted multi-line string suitable for injection into
        an agent's system or user prompt.

        Args:
            query:          Query to search with.
            top_k:          Number of chunks to retrieve.
            min_similarity: Minimum similarity score (filters low-quality results).

        Returns:
            Formatted context string, or empty string if nothing relevant found.
        """
        result = self.retrieve(query, top_k)

        # Filter by minimum similarity
        relevant = [r for r in result.results if r.similarity_score >= min_similarity]

        if not relevant:
            logger.debug(
                "No knowledge chunks above similarity %.2f for query '%.40s'.",
                min_similarity,
                query,
            )
            return ""

        lines = ["--- Relevant Knowledge Base Excerpts ---"]
        for i, chunk in enumerate(relevant, start=1):
            source = chunk.metadata.get("meta_source_name", "Unknown Source")
            score = f"{chunk.similarity_score:.2f}"
            lines.append(f"\n[{i}] Source: {source} (relevance: {score})")
            lines.append(chunk.content)

        lines.append("\n--- End of Knowledge Base Excerpts ---")
        return "\n".join(lines)

    def knowledge_count(self) -> int:
        """Return total number of knowledge chunks for this domain."""
        return self._store.count(self._domain, MemoryType.SEMANTIC)
