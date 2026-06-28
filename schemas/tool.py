"""
schemas/tool.py

Runtime models for tool invocations — the contract between agents and tools.

Tools are the atomic units of capability. Agents request tool calls via
ToolCall, and the tool registry executes them and returns ToolResult.
ToolError is used when a tool fails gracefully (as opposed to an exception).

Design:
    - ToolCall represents an agent's intent to call a tool with arguments.
    - ToolResult carries the structured output and execution metadata.
    - ToolError provides structured error information without stack traces
      (those are logged separately).
    - ToolExecutionLog aggregates all tool calls in a single workflow run
      for audit/explainability purposes.
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


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Tool I/O models
# ---------------------------------------------------------------------------


class ToolCall(BaseModel, frozen=True):
    """
    An agent's request to invoke a specific tool.

    Produced by the agent when the LLM decides to call a tool.
    Consumed by the tool registry which resolves and executes the tool.
    """

    call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = Field(description="The tool name as defined in the domain config.")
    arguments: dict[str, Any] = Field(
        description="Arguments to pass to the tool, keyed by parameter name."
    )
    agent_name: str = Field(description="Name of the agent making this call.")
    domain: str = Field(description="Domain context for this call.")
    run_id: str = Field(default="", description="Workflow run ID for correlation.")
    requested_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ToolResult(BaseModel):
    """
    The result of a successful or failed tool invocation.

    Whether a tool succeeds or fails, a ToolResult is always returned.
    Failed results set status=ERROR and populate the error field.
    """

    call_id: str = Field(description="ID of the originating ToolCall.")
    tool_name: str
    agent_name: str
    domain: str
    status: ToolStatus = Field(default=ToolStatus.SUCCESS)

    # Successful result
    data: Any = Field(
        default=None,
        description="Primary structured output of the tool.",
    )
    summary: str = Field(
        default="",
        description="Human-readable one-sentence summary of the result.",
    )

    # Error information (populated when status != SUCCESS)
    error_type: str | None = Field(default=None)
    error_message: str | None = Field(default=None)

    # Performance metadata
    execution_time_ms: int | None = Field(
        default=None,
        description="Wall-clock execution time in milliseconds.",
    )
    records_returned: int = Field(
        default=0,
        description="Number of records/items in the data field (if applicable).",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    executed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        return self.status == ToolStatus.ERROR


class ToolExecutionLog(BaseModel):
    """
    Aggregated log of all tool calls made during a single workflow run.

    Stored in WorkflowState and surfaced in the UI for explainability.
    """

    run_id: str
    domain: str
    calls: list[ToolCall] = Field(default_factory=list)
    results: list[ToolResult] = Field(default_factory=list)

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.is_success)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.is_error)

    @property
    def tool_names_used(self) -> list[str]:
        return list(dict.fromkeys(c.tool_name for c in self.calls))

    def get_results_for_tool(self, tool_name: str) -> list[ToolResult]:
        return [r for r in self.results if r.tool_name == tool_name]
