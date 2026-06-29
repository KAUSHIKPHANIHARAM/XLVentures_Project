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

        # When no data is pre-loaded in state, tell the model to use tools
        if not data_ctx:
            tool_instruction = (
                "IMPORTANT: You MUST call your tools immediately — do NOT ask the user for clarification.\n"
                "Available tools:\n"
                "- search_customers(query='', segment='', min_churn_risk=0.0, limit=20)\n"
                "  e.g. search_customers(segment='Premium', min_churn_risk=0.7) for Premium high-risk customers\n"
                "- analyze_churn_risk(customer_id='CUST-002')\n"
                "- get_customer_detail(customer_id='CUST-002')\n"
                "- get_interaction_history(customer_id='CUST-002', limit=10)\n"
                "NEVER ask for clarification. Infer the right tool call from the user query."
            )
            extra = tool_instruction + ("\n\n" + extra if extra else "")

        return [
            self._system_message(extra),
            HumanMessage(
                content=f"Use your tools to retrieve data, then analyse:\n{user_query}"
            ),
        ]

    def _state_updates(self, output, state: WorkflowState) -> dict[str, Any]:
        existing = list(state.get("retrieved_data", []))
        existing.extend(output.retrieved_data)
        return {"retrieved_data": existing}
