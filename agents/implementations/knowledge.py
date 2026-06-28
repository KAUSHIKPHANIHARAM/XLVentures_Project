"""
agents/implementations/knowledge.py

KnowledgeAgent — answers questions using the domain knowledge base.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from agents.base import BaseAgent
from schemas.agent import WorkflowState


class KnowledgeAgent(BaseAgent):
    """Retrieves and synthesises domain knowledge via semantic search."""

    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        user_query = state.get("user_query", "")
        knowledge_ctx = self._knowledge_context_block(state)

        return [
            self._system_message(knowledge_ctx),
            HumanMessage(
                content=(
                    f"Using the knowledge base excerpts above, answer:\n{user_query}\n\n"
                    f"If the knowledge base does not contain a relevant answer, "
                    f"clearly state that and suggest where the user might look."
                )
            ),
        ]

    def _state_updates(self, output, state: WorkflowState) -> dict[str, Any]:
        return {}
