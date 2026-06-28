"""
agents/implementations/analysis.py

AnalysisAgent — performs analytical reasoning on retrieved customer data.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from agents.base import BaseAgent
from schemas.agent import WorkflowState


class AnalysisAgent(BaseAgent):
    """Analyses churn risk, sentiment, and behavioural patterns."""

    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        user_query = state.get("user_query", "")
        data_ctx = self._data_context_block(state)
        knowledge_ctx = self._knowledge_context_block(state)

        context_parts = []
        if data_ctx:
            context_parts.append(data_ctx)
        if knowledge_ctx:
            context_parts.append(knowledge_ctx)

        extra = "\n\n".join(context_parts)

        return [
            self._system_message(extra),
            HumanMessage(
                content=f"Analyse the following request using the data above:\n{user_query}"
            ),
        ]

    def _state_updates(self, output, state: WorkflowState) -> dict[str, Any]:
        existing = list(state.get("retrieved_data", []))
        existing.extend(output.retrieved_data)
        return {"retrieved_data": existing}
