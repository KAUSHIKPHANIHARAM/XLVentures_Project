"""
agents/implementations/decision.py

DecisionAgent — generates explainable, actionable recommendations.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

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

        # If no data yet, instruct the model to call its tools FIRST
        if not data_ctx:
            tool_instruction = (
                "IMPORTANT: You MUST call your tools to retrieve data FIRST — do NOT ask the user for clarification.\n"
                "Available tools:\n"
                "- search_customers(query='', segment='', min_churn_risk=0.0, limit=20)\n"
                "  e.g. search_customers(segment='Premium', min_churn_risk=0.7) for high-risk premium customers\n"
                "- get_customer_detail(customer_id='CUST-002')\n"
                "- analyze_churn_risk(customer_id='CUST-002')\n"
                "- generate_decision_recommendation(customer_id='CUST-002', context='')\n"
                "- get_interaction_history(customer_id='CUST-002', limit=10)\n"
                "NEVER say you need more information. Infer parameters from the query and call tools immediately."
            )
            extra = tool_instruction + ("\n\n" + extra if extra else "")

        return [
            self._system_message(extra),
            HumanMessage(
                content=(
                    f"Use your tools to retrieve all relevant customer data, then "
                    f"provide a full decision recommendation for:\n{user_query}"
                )
            ),
        ]

    def _state_updates(self, output, state: WorkflowState) -> dict[str, Any]:
        existing = list(state.get("retrieved_data", []))
        existing.extend(output.retrieved_data)
        return {"retrieved_data": existing}
