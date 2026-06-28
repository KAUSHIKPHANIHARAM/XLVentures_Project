"""
agents/implementations/synthesizer.py

SynthesizerAgent — combines all specialist agent outputs into a final response.

This is always the terminal node of the workflow. It reads all AgentOutput
objects from WorkflowState, plus the original user query, and produces a
single coherent, formatted response for the end user. No tools.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from agents.base import BaseAgent
from schemas.agent import AgentOutput, AgentStatus, WorkflowState
from utils.logging import get_logger

logger = get_logger(__name__)


class SynthesizerAgent(BaseAgent):
    """Synthesises all agent outputs into a final user-facing response."""

    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        user_query = state.get("user_query", "")
        agent_outputs: dict[str, AgentOutput] = state.get("agent_outputs", {})

        # Collect non-empty specialist responses (exclude router + synthesizer)
        specialist_responses: list[str] = []
        for agent_name, output in agent_outputs.items():
            if agent_name in ("router_agent", "synthesizer_agent"):
                continue
            if output.response and output.status == AgentStatus.COMPLETED:
                specialist_responses.append(
                    f"=== {agent_name.replace('_', ' ').title()} Output ===\n"
                    f"{output.response[:1500]}"
                )

        if not specialist_responses:
            specialist_responses = ["No specialist agent produced output."]

        combined = "\n\n".join(specialist_responses)

        return [
            self._system_message(),
            HumanMessage(
                content=(
                    f"Original user question:\n{user_query}\n\n"
                    f"Specialist agent outputs to synthesise:\n\n{combined}\n\n"
                    f"Provide a single, coherent, well-formatted response to the user."
                )
            ),
        ]

    def _state_updates(
        self, output: AgentOutput, state: WorkflowState
    ) -> dict[str, Any]:
        """Write the final response to state."""
        from utils.datetime_utils import utc_now_iso
        return {
            "final_response": output.response,
            "workflow_status": "completed",
            "completed_at": utc_now_iso(),
        }
