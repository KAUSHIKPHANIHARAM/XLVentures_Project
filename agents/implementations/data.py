"""
agents/implementations/data.py

DataAgent — retrieves structured data from the connector layer via tools.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from agents.base import BaseAgent
from schemas.agent import WorkflowState


class DataAgent(BaseAgent):
    """Retrieves customer data using search and lookup tools."""

    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        user_query = state.get("user_query", "")
        extra = self._knowledge_context_block(state)
        return [
            self._system_message(extra),
            HumanMessage(content=f"Request: {user_query}"),
        ]

    def _state_updates(self, output, state: WorkflowState) -> dict[str, Any]:
        """Merge newly retrieved data into state."""
        existing = list(state.get("retrieved_data", []))
        existing.extend(output.retrieved_data)
        return {"retrieved_data": existing}
