"""
schemas/__init__.py

Public API for the schemas module.

All runtime data models exported from a single namespace.
Every other module imports schemas from here — never from submodules directly.

Example:
    from schemas import AgentInput, AgentOutput, WorkflowState
    from schemas import DecisionResult, Recommendation
    from schemas import UserQuery, IntentResult
    from schemas import MemoryEntry, RetrievalResult
    from schemas import EntityRecord, EntitySearchResult
    from schemas import ToolCall, ToolResult
"""

# Agent schemas
from schemas.agent import (
    AgentInput,
    AgentOutput,
    AgentRole,
    AgentStatus,
    WorkflowState,
)

# Query schemas
from schemas.query import (
    IntentResult,
    PlanStep,
    PlannerOutput,
    PlanStepStatus,
    QueryType,
    UserQuery,
)

# Decision schemas
from schemas.decision import (
    ConfidenceLevel,
    DecisionRequest,
    DecisionResult,
    DecisionStatus,
    Evidence,
    Recommendation,
    RiskFlag,
    RiskLevel,
)

# Memory schemas
from schemas.memory import (
    KnowledgeChunk,
    MemoryEntry,
    MemoryType,
    RetrievalResult,
    RetrievedMemory,
)

# Entity schemas
from schemas.entity import (
    EntityCreateRequest,
    EntityRecord,
    EntitySearchResult,
    EntityUpdateRequest,
)

# Tool schemas
from schemas.tool import (
    ToolCall,
    ToolExecutionLog,
    ToolResult,
    ToolStatus,
)

__all__ = [
    # Agent
    "AgentInput",
    "AgentOutput",
    "AgentRole",
    "AgentStatus",
    "WorkflowState",
    # Query
    "UserQuery",
    "IntentResult",
    "QueryType",
    "PlanStep",
    "PlanStepStatus",
    "PlannerOutput",
    # Decision
    "DecisionRequest",
    "DecisionResult",
    "DecisionStatus",
    "Recommendation",
    "ConfidenceLevel",
    "RiskLevel",
    "RiskFlag",
    "Evidence",
    # Memory
    "MemoryEntry",
    "MemoryType",
    "RetrievedMemory",
    "RetrievalResult",
    "KnowledgeChunk",
    # Entity
    "EntityRecord",
    "EntitySearchResult",
    "EntityUpdateRequest",
    "EntityCreateRequest",
    # Tool
    "ToolCall",
    "ToolResult",
    "ToolStatus",
    "ToolExecutionLog",
]
