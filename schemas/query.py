"""
schemas/query.py

Runtime models for user queries, intent classification, and planner output.

These models represent the earliest stage of the pipeline — capturing the
raw user request and the planner's structured interpretation of it before
any agent is invoked.

Design:
    - UserQuery wraps the raw string with session context.
    - IntentResult carries the router agent's routing decision.
    - PlannerOutput represents a decomposed multi-step task plan (used by
      the planner module when a query requires multiple agents in sequence).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class QueryType(str, Enum):
    """Broad category of user query — set by the planner."""

    DATA_RETRIEVAL = "data_retrieval"
    ANALYSIS = "analysis"
    DECISION = "decision"
    KNOWLEDGE = "knowledge"
    CONVERSATIONAL = "conversational"
    UNKNOWN = "unknown"


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Query models
# ---------------------------------------------------------------------------


class UserQuery(BaseModel, frozen=True):
    """
    Represents a single user query entering the platform.

    Carries the raw text, session context, and domain override capability.
    This is the entrypoint object — created at the UI/API boundary and
    passed into the workflow engine.
    """

    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(description="The raw, unmodified user input text.")
    domain: str = Field(
        description="Target domain for this query (e.g. 'customer_management')."
    )
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session identifier for grouping related queries.",
    )
    user_id: str | None = Field(
        default=None,
        description="Optional user identifier for personalization/audit.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary context (e.g. UI source, filters, user preferences).",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query text cannot be empty.")
        return v.strip()


class IntentResult(BaseModel, frozen=True):
    """
    The router agent's structured interpretation of a user query.

    Produced by the router_agent and used by the workflow engine to decide
    which specialist agent to invoke next.
    """

    query_id: str = Field(description="ID of the originating UserQuery.")
    intent: str = Field(description="Brief description of the user's intent.")
    query_type: QueryType = Field(description="Broad category of the query.")
    target_agent: str = Field(
        description="Name of the specialist agent to handle this query."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="One-sentence explanation of routing decision.")
    extracted_entities: dict[str, Any] = Field(
        default_factory=dict,
        description="Entities extracted from the query (e.g. customer_id, name).",
    )
    requires_multi_agent: bool = Field(
        default=False,
        description="True when the query requires more than one specialist agent.",
    )


class PlanStep(BaseModel):
    """
    A single step in a multi-agent execution plan.

    Used by the planner when a complex query requires sequential or
    parallel execution of multiple agents.
    """

    step_index: int = Field(description="Zero-based position in the plan.")
    agent_name: str = Field(description="Agent responsible for this step.")
    description: str = Field(description="What this step should accomplish.")
    depends_on: list[int] = Field(
        default_factory=list,
        description="Step indices that must complete before this step starts.",
    )
    status: PlanStepStatus = Field(default=PlanStepStatus.PENDING)
    input_keys: list[str] = Field(
        default_factory=list,
        description="State keys this step will read from WorkflowState.",
    )
    output_keys: list[str] = Field(
        default_factory=list,
        description="State keys this step will write to WorkflowState.",
    )


class PlannerOutput(BaseModel):
    """
    The planner's decomposed execution plan for a user query.

    For simple queries, this contains a single step.
    For complex queries (e.g. 'analyse + recommend'), it chains multiple steps.
    """

    query_id: str
    domain: str
    intent: IntentResult
    steps: list[PlanStep] = Field(default_factory=list)
    estimated_complexity: str = Field(
        default="simple",
        description="Complexity label: simple, moderate, complex.",
    )
    reasoning: str = Field(default="")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def is_multi_step(self) -> bool:
        return len(self.steps) > 1

    @property
    def agent_sequence(self) -> list[str]:
        """Ordered list of agent names to invoke."""
        return [step.agent_name for step in sorted(self.steps, key=lambda s: s.step_index)]
