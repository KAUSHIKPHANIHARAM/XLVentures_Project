"""
schemas/decision.py

Runtime models for the decision engine's outputs.

The decision engine is the highest-value component of the platform.
These models carry structured, explainable recommendations that account
managers and business users act on.

Design:
    - Every decision is explainable: it carries evidence, confidence, and
      alternative options — not just a bare answer.
    - DecisionResult is the primary output model: it groups one or more
      Recommendation objects with audit metadata.
    - RiskLevel and ConfidenceLevel use string enums for JSON/YAML safety.
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


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class DecisionStatus(str, Enum):
    APPROVED = "approved"       # Recommended with high confidence
    ADVISORY = "advisory"       # Recommended but requires human review
    ESCALATE = "escalate"       # Issue requires escalation
    INSUFFICIENT_DATA = "insufficient_data"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------


class Evidence(BaseModel, frozen=True):
    """
    A single piece of evidence supporting a recommendation.

    Enables full explainability — users can trace exactly why
    a recommendation was made.
    """

    source: str = Field(
        description="Where this evidence came from: 'database', 'knowledge_base', 'analysis'."
    )
    description: str = Field(description="Human-readable description of the evidence.")
    data: Any = Field(
        default=None,
        description="Raw data point (value, score, record) supporting this evidence.",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relative importance of this evidence in the decision (0.0–1.0).",
    )


class RiskFlag(BaseModel, frozen=True):
    """A risk or caveat associated with a recommendation."""

    level: RiskLevel
    description: str = Field(description="Human-readable risk description.")
    mitigation: str = Field(
        default="",
        description="Suggested action to mitigate this risk.",
    )


class Recommendation(BaseModel, frozen=True):
    """
    A single, actionable recommendation produced by the decision engine.

    Every recommendation must be: specific, evidenced, and bounded by
    a confidence level and any associated risks.
    """

    recommendation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )
    action: str = Field(
        description="The specific, actionable recommendation (imperative sentence)."
    )
    rationale: str = Field(
        description="Evidence-based explanation of why this action is recommended."
    )
    confidence_level: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Numerical confidence score (0.0–1.0).",
    )
    priority: int = Field(
        default=1,
        ge=1,
        description="Ranking among recommendations (1 = highest priority).",
    )
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="Supporting evidence for this recommendation.",
    )
    risk_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Risks or caveats associated with this recommendation.",
    )
    estimated_impact: str = Field(
        default="",
        description="Expected outcome if this recommendation is followed.",
    )
    time_sensitivity: str = Field(
        default="",
        description="Urgency indicator (e.g. 'Within 48 hours', 'Next quarter').",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level decision models
# ---------------------------------------------------------------------------


class DecisionRequest(BaseModel, frozen=True):
    """
    Input to the decision engine.

    Packages everything the engine needs: the domain context, entity in question,
    user question, pre-retrieved data, and knowledge chunks.
    """

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: str = Field(description="Domain this decision belongs to.")
    entity_type: str = Field(
        description="Type of entity being evaluated (e.g. 'Customer')."
    )
    entity_id: str | int | None = Field(
        default=None,
        description="ID of the specific entity being evaluated.",
    )
    question: str = Field(
        description="The decision question being asked (the user's intent)."
    )
    entity_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured entity data retrieved from the database.",
    )
    analysis_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results from prior analysis agent invocations.",
    )
    knowledge_context: list[str] = Field(
        default_factory=list,
        description="Relevant knowledge base chunks for this decision.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DecisionResult(BaseModel):
    """
    The complete output of the decision engine for a single request.

    Contains ranked recommendations, overall status, and full audit trail.
    This is the model that gets persisted, displayed in the UI, and
    potentially used for downstream automation.
    """

    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = Field(description="ID of the originating DecisionRequest.")
    domain: str
    entity_type: str
    entity_id: str | int | None = None

    status: DecisionStatus = Field(default=DecisionStatus.APPROVED)
    overall_risk: RiskLevel = Field(default=RiskLevel.NONE)
    summary: str = Field(
        description="One-paragraph summary of the decision situation and top recommendation."
    )
    recommendations: list[Recommendation] = Field(
        default_factory=list,
        description="Ranked list of recommendations (index 0 = highest priority).",
    )
    alternative_options: list[str] = Field(
        default_factory=list,
        description="Alternative courses of action not taken as primary recommendations.",
    )
    requires_human_review: bool = Field(
        default=False,
        description="True when the system cannot make a high-confidence recommendation.",
    )
    reasoning_chain: list[str] = Field(
        default_factory=list,
        description="Step-by-step reasoning trace for full explainability.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def top_recommendation(self) -> Recommendation | None:
        """Return the highest-priority recommendation, or None if empty."""
        if not self.recommendations:
            return None
        return min(self.recommendations, key=lambda r: r.priority)
