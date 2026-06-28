"""
agents/implementations/decision.py

DecisionAgent — generates explainable, actionable recommendations.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from agents.base import BaseAgent
from schemas.agent import WorkflowState


class DecisionAgent(BaseAgent):
    """Produces structured decision recommendations grounded in data and knowledge."""

    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        user_query = state.get("user_query", "")
        data_ctx = self._data_context_block(state)
        knowledge_ctx = self._knowledge_context_block(state)

        context_parts = []
        if data_ctx:
            context_parts.append(data_ctx)
        if knowledge_ctx:
            context_parts.append(knowledge_ctx)

        # Include prior agent analysis if available
        agent_outputs = state.get("agent_outputs", {})
        if "analysis_agent" in agent_outputs:
            analysis_text = agent_outputs["analysis_agent"].response
            context_parts.append(
                f"--- Prior Analysis ---\n{analysis_text[:800]}\n--- End Analysis ---"
            )

        extra = "\n\n".join(context_parts)

        return [
            self._system_message(extra),
            HumanMessage(
                content=(
                    f"Based on all the above context and data, provide your "
                    f"decision recommendation for:\n{user_query}"
                )
            ),
        ]

    def _state_updates(self, output, state: WorkflowState) -> dict[str, Any]:
        existing = list(state.get("retrieved_data", []))
        existing.extend(output.retrieved_data)
        return {"retrieved_data": existing}
