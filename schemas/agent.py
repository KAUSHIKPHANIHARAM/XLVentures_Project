"""
schemas/agent.py

Runtime data models for agent inputs, outputs, and the LangGraph workflow state.

These models define what flows through the graph at runtime. They are
completely domain-agnostic — domain-specific data is carried as generic
dicts inside the 'context' and 'data' fields.

Design:
    - WorkflowState is a TypedDict (required by LangGraph for graph state).
    - AgentInput / AgentOutput use frozen Pydantic models for safety.
    - All timestamps use ISO-8601 strings for simplicity (no tz complexity).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentRole(str, Enum):
    """Canonical roles an agent can play in the workflow."""

    ROUTER = "router"
    DATA_RETRIEVAL = "data_retrieval"
    ANALYST = "analyst"
    DECISION_MAKER = "decision_maker"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    SYNTHESIZER = "synthesizer"


class AgentStatus(str, Enum):
    """Execution status of an agent invocation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Agent I/O models
# ---------------------------------------------------------------------------


class AgentInput(BaseModel, frozen=True):
    """
    Structured input passed to every agent node in the LangGraph graph.

    Carries the original user query, accumulated context from prior agents,
    domain name, and any structured data retrieved so far.
    """

    run_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this workflow run.",
    )
    domain: str = Field(description="Active domain name (e.g. 'customer_management').")
    user_query: str = Field(description="The original unmodified user query.")
    agent_name: str = Field(description="Name of the agent receiving this input.")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Accumulated context from prior agent outputs in this run.",
    )
    retrieved_data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured data retrieved from tools or connectors.",
    )
    knowledge_chunks: list[str] = Field(
        default_factory=list,
        description="Relevant knowledge base excerpts retrieved via semantic search.",
    )
    memory_entries: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Relevant past interactions from episodic memory.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary pass-through metadata (e.g. user session info).",
    )

    @field_validator("user_query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_query cannot be empty or whitespace.")
        return v.strip()


class AgentOutput(BaseModel):
    """
    Structured output produced by every agent node in the LangGraph graph.

    The 'response' is the agent's primary text output.
    The 'next_agent' field drives conditional routing in the graph.
    """

    agent_name: str = Field(description="Name of the agent that produced this output.")
    status: AgentStatus = Field(default=AgentStatus.COMPLETED)
    response: str = Field(
        description="Primary text response from the agent (may be empty for routers)."
    )
    next_agent: str | None = Field(
        default=None,
        description="For router agents: name of the next agent to invoke.",
    )
    tool_calls_made: list[str] = Field(
        default_factory=list,
        description="Names of tools called during this agent's execution.",
    )
    retrieved_data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured data collected by tools during this invocation.",
    )
    knowledge_chunks: list[str] = Field(
        default_factory=list,
        description="Knowledge base excerpts surfaced during this invocation.",
    )
    reasoning: str = Field(
        default="",
        description="Agent's chain-of-thought reasoning (for explainability).",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Agent's self-reported confidence in its output.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if status is FAILED.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# LangGraph workflow state (TypedDict — required by LangGraph)
# ---------------------------------------------------------------------------


class WorkflowState(TypedDict, total=False):
    """
    The shared mutable state that flows through the entire LangGraph graph.

    LangGraph requires a TypedDict for graph state. Every node reads from
    and writes to this dict. Fields are optional (total=False) because
    early nodes won't have data from later nodes yet.

    All agents receive the full state and add their output to it.
    """

    # Identity
    run_id: str
    domain: str
    session_id: str

    # User input
    user_query: str
    metadata: dict[str, Any]

    # Routing
    intent: str
    target_agent: str
    routing_confidence: float
    routing_reasoning: str

    # Data layer
    retrieved_data: list[dict[str, Any]]
    knowledge_chunks: list[str]
    memory_entries: list[dict[str, Any]]

    # Agent outputs (keyed by agent name)
    agent_outputs: dict[str, AgentOutput]

    # Final synthesis
    final_response: str
    workflow_status: str
    error: str | None

    # Audit / explainability
    execution_trace: list[dict[str, Any]]
    total_tool_calls: int
    started_at: str
    completed_at: str
