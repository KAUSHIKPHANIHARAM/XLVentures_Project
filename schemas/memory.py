"""
schemas/memory.py

Runtime models for the memory and knowledge retrieval layer.

The platform has two distinct memory systems:
    1. Episodic memory — past interactions with the same user/entity,
       stored and retrieved from ChromaDB.
    2. Knowledge memory — domain knowledge (policies, playbooks) also
       stored in ChromaDB, but treated as static reference material.

These models are the contracts between the memory module (ChromaDB)
and the agents that consume retrieved context.

Design:
    - MemoryType distinguishes episodic vs. semantic (knowledge) memory.
    - MemoryEntry is what gets stored INTO ChromaDB.
    - RetrievalResult is what comes OUT of ChromaDB queries.
    - KnowledgeChunk represents a processed, chunked knowledge document.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MemoryType(str, Enum):
    """
    Classification of memory entries.

    EPISODIC: Interaction-level memory — what happened in past conversations.
    SEMANTIC: Domain knowledge — policies, playbooks, reference material.
    WORKING:  Short-lived in-context memory within a single workflow run.
    """

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"


# ---------------------------------------------------------------------------
# Storage models (what goes INTO memory)
# ---------------------------------------------------------------------------


class MemoryEntry(BaseModel):
    """
    A single entry stored in the vector memory system (ChromaDB).

    The 'content' field is embedded and stored as a vector.
    The 'metadata' dict is stored as ChromaDB document metadata
    and used for filtering during retrieval.
    """

    entry_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier used as ChromaDB document ID.",
    )
    memory_type: MemoryType = Field(description="Episodic, semantic, or working.")
    domain: str = Field(description="Domain this memory belongs to.")
    content: str = Field(
        description="The text that will be embedded and stored in ChromaDB."
    )
    entity_type: str | None = Field(
        default=None,
        description="Entity type this memory relates to (e.g. 'Customer').",
    )
    entity_id: str | None = Field(
        default=None,
        description="Specific entity ID this memory relates to.",
    )
    session_id: str | None = Field(
        default=None,
        description="Session that generated this memory (for episodic entries).",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorical tags for metadata filtering.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured metadata stored alongside the vector.",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_chroma_metadata(self) -> dict[str, Any]:
        """
        Convert to a flat dict suitable for ChromaDB's metadata field.

        ChromaDB metadata must be flat (no nested dicts or lists).
        """
        return {
            "entry_id": self.entry_id,
            "memory_type": self.memory_type.value,
            "domain": self.domain,
            "entity_type": self.entity_type or "",
            "entity_id": self.entity_id or "",
            "session_id": self.session_id or "",
            "tags": ",".join(self.tags),
            "created_at": self.created_at,
            **{
                f"meta_{k}": str(v)
                for k, v in self.metadata.items()
                if isinstance(v, (str, int, float, bool))
            },
        }


# ---------------------------------------------------------------------------
# Retrieval models (what comes OUT of memory)
# ---------------------------------------------------------------------------


class RetrievedMemory(BaseModel, frozen=True):
    """
    A single result from a ChromaDB similarity search.

    Wraps the stored content with its similarity score and provenance.
    """

    entry_id: str
    content: str = Field(description="The stored text that was retrieved.")
    similarity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Cosine similarity score (1.0 = exact match).",
    )
    memory_type: MemoryType
    domain: str
    entity_type: str | None = None
    entity_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class RetrievalResult(BaseModel, frozen=True):
    """
    The result of a single ChromaDB retrieval query.

    Aggregates all retrieved memories for a given query, ordered by score.
    """

    query: str = Field(description="The query that was issued.")
    domain: str
    memory_type: MemoryType | None = Field(
        default=None,
        description="If set, only this type was queried.",
    )
    results: list[RetrievedMemory] = Field(
        default_factory=list,
        description="Retrieved memories ordered by similarity descending.",
    )
    total_found: int = Field(default=0)
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def top_result(self) -> RetrievedMemory | None:
        return self.results[0] if self.results else None

    @property
    def content_list(self) -> list[str]:
        """Plain list of content strings — convenient for injecting into prompts."""
        return [r.content for r in self.results]


# ---------------------------------------------------------------------------
# Knowledge chunk model (intermediate model during knowledge ingestion)
# ---------------------------------------------------------------------------


class KnowledgeChunk(BaseModel, frozen=True):
    """
    A single chunk produced during knowledge document ingestion.

    Knowledge documents are split into chunks before embedding.
    This model represents one chunk before it becomes a MemoryEntry.
    """

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = Field(description="Name of the knowledge source.")
    domain: str
    content: str = Field(description="Chunk text content.")
    chunk_index: int = Field(description="Zero-based index within the source document.")
    total_chunks: int = Field(description="Total number of chunks from the source.")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_memory_entry(self) -> MemoryEntry:
        """Convert this chunk to a MemoryEntry for storage in ChromaDB."""
        return MemoryEntry(
            entry_id=self.chunk_id,
            memory_type=MemoryType.SEMANTIC,
            domain=self.domain,
            content=self.content,
            tags=self.tags,
            metadata={
                "source_name": self.source_name,
                "chunk_index": self.chunk_index,
                "total_chunks": self.total_chunks,
                **self.metadata,
            },
        )
