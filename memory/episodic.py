"""
memory/episodic.py

EpisodicMemory — records and retrieves past agent interaction memories.

Episodic memory answers: "What happened in past conversations about this
customer / entity?" Agents use it to avoid repeating questions and to
build context from previous sessions.

Design:
    - Records one MemoryEntry per agent output (after each workflow run).
    - Retrieves the most relevant past interactions for a given query/entity.
    - Entries are tagged with session_id, entity_id, and agent_name.
    - Retrieval uses semantic similarity + optional entity_id filter.
"""

from __future__ import annotations

import logging

from memory.base import AbstractMemoryStore
from schemas.agent import AgentOutput
from schemas.memory import MemoryEntry, MemoryType, RetrievalResult
from utils.datetime_utils import utc_now_iso
from utils.logging import get_logger
from utils.text import truncate_text

logger = get_logger(__name__)

# Maximum content length per episodic entry (keeps embedding costs low)
_MAX_EPISODIC_CONTENT = 1000


class EpisodicMemory:
    """
    Records agent outputs as episodic memories and retrieves relevant history.

    Args:
        store:  The AbstractMemoryStore (ChromaDB) to read from / write to.
        domain: Domain this episodic memory serves.
    """

    def __init__(self, store: AbstractMemoryStore, domain: str) -> None:
        self._store = store
        self._domain = domain

    def record(
        self,
        session_id: str,
        agent_output: AgentOutput,
        user_query: str,
        entity_id: str | None = None,
        entity_type: str | None = None,
    ) -> str:
        """
        Store an agent output as an episodic memory.

        The content stored is a structured summary of the interaction,
        not the raw agent response, to keep embedding quality high.

        Args:
            session_id:   Current workflow session ID.
            agent_output: The AgentOutput to record.
            user_query:   The original user query that triggered this output.
            entity_id:    ID of the primary entity involved (if any).
            entity_type:  Type of the entity (e.g. 'Customer').

        Returns:
            The entry_id of the stored memory.
        """
        content = self._format_episodic_content(user_query, agent_output)
        content = truncate_text(content, max_length=_MAX_EPISODIC_CONTENT)

        entry = MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            domain=self._domain,
            content=content,
            entity_type=entity_type,
            entity_id=entity_id,
            session_id=session_id,
            tags=["interaction", agent_output.agent_name],
            metadata={
                "agent_name": agent_output.agent_name,
                "user_query": truncate_text(user_query, 200),
                "confidence": str(agent_output.confidence),
                "tool_calls": ",".join(agent_output.tool_calls_made),
            },
        )

        entry_id = self._store.store(entry)
        logger.debug(
            "Recorded episodic memory for session='%s' agent='%s'.",
            session_id,
            agent_output.agent_name,
        )
        return entry_id

    def retrieve_relevant(
        self,
        query: str,
        top_k: int = 5,
        entity_id: str | None = None,
        entity_type: str | None = None,
    ) -> RetrievalResult:
        """
        Retrieve past interactions most relevant to the current query.

        Args:
            query:       Current user query to find relevant history for.
            top_k:       Max number of past memories to retrieve.
            entity_id:   If set, filter to interactions involving this entity.
            entity_type: If set, filter to interactions involving this entity type.

        Returns:
            RetrievalResult with ranked past interactions.
        """
        filters: dict[str, str] = {}
        if entity_id:
            filters["entity_id"] = entity_id
        if entity_type:
            filters["entity_type"] = entity_type

        result = self._store.retrieve(
            query=query,
            domain=self._domain,
            memory_type=MemoryType.EPISODIC,
            top_k=top_k,
            filters=filters or None,
        )

        logger.debug(
            "Episodic retrieval: query='%.40s' found=%d entity_filter=%s",
            query,
            result.total_found,
            entity_id,
        )
        return result

    def entry_count(self) -> int:
        """Return total number of episodic memories for this domain."""
        return self._store.count(self._domain, MemoryType.EPISODIC)

    @staticmethod
    def _format_episodic_content(query: str, output: AgentOutput) -> str:
        """Format a structured content string for embedding."""
        parts = [
            f"User asked: {query}",
            f"Agent ({output.agent_name}) responded: {output.response[:500]}",
        ]
        if output.reasoning:
            parts.append(f"Reasoning: {output.reasoning[:200]}")
        if output.tool_calls_made:
            parts.append(f"Tools used: {', '.join(output.tool_calls_made)}")
        return "\n".join(parts)
