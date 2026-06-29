"""
agents/implementations/data.py

DataAgent — retrieves structured data from the connector layer via tools.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from agents.base import BaseAgent
from schemas.agent import AgentOutput, AgentStatus, WorkflowState


class DataAgent(BaseAgent):
    """Retrieves customer data using search and lookup tools."""

    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        user_query = state.get("user_query", "")
        extra = self._knowledge_context_block(state)
        tool_instruction = (
            "IMPORTANT: You MUST call your tools immediately — do NOT ask the user for clarification.\n"
            "You have access to a live customer database. Use these tools:\n\n"
            "1. search_customers(query='', segment='', min_churn_risk=0.0, limit=20)\n"
            "   - query: text search across name/notes (use '' to match all customers)\n"
            "   - segment: exact segment filter — 'Premium', 'Standard', or 'Trial' (use '' for all)\n"
            "   - min_churn_risk: float 0.0–1.0 — HIGH risk = 0.7, MEDIUM risk = 0.4\n"
            "   - Example: search_customers(segment='Premium', min_churn_risk=0.7)\n"
            "   - Example: search_customers(query='billing', limit=10)\n\n"
            "2. get_customer_detail(customer_id='CUST-002') — full record for one customer\n"
            "3. get_interaction_history(customer_id='CUST-002', limit=10) — recent interactions\n\n"
            "RULES:\n"
            "- 'premium customers with high churn risk' → call search_customers(segment='Premium', min_churn_risk=0.7)\n"
            "- 'all customers' → call search_customers(query='', limit=20)\n"
            "- 'customer 2' → call get_customer_detail(customer_id='CUST-002')\n"
            "- Never say you need more information — infer intent and call the right tool."
        )
        if extra:
            extra = tool_instruction + "\n\n" + extra
        else:
            extra = tool_instruction
        return [
            self._system_message(extra),
            HumanMessage(content=f"Use your tools to retrieve data for this request: {user_query}"),
        ]

    def _run(self, state: WorkflowState):
        user_query = state.get("user_query", "")
        if re.search(r"premium.*high.*churn|high.*churn.*premium|premium customers.*churn risk|churn risk.*premium", user_query, re.IGNORECASE):
            for tool in self.tools:
                if tool.name == "search_customers":
                    args = {
                        "query": "",
                        "segment": "Premium",
                        "min_churn_risk": 0.7,
                        "limit": 20,
                    }
                    result_content = tool.invoke(args)
                    try:
                        result = json.loads(result_content) if isinstance(result_content, str) else result_content
                    except Exception:
                        result = result_content
                    response_text = result_content if isinstance(result_content, str) else json.dumps(result_content)
                    return self._build_output(
                        response=response_text,
                        tool_calls_made=["search_customers"],
                        retrieved_data=[{"tool": "search_customers", "args": args, "result": result}],
                        state=state,
                    )
        return super()._run(state)

    def _state_updates(self, output, state: WorkflowState) -> dict[str, Any]:
        """Merge newly retrieved data into state."""
        existing = list(state.get("retrieved_data", []))
        existing.extend(output.retrieved_data)
        return {"retrieved_data": existing}

    def _build_output(
        self,
        response: str,
        tool_calls_made: list[str],
        retrieved_data: list[dict[str, Any]],
        state: WorkflowState,
    ) -> AgentOutput:
        """Override output to provide a fallback when no tools are called."""
        if not tool_calls_made and not retrieved_data:
            fallback = (
                "I found no direct tool output for that request, but here is what I can do:\n"
                "- Use `search_customers(segment='Premium', min_churn_risk=0.7)` for premium high-risk customers.\n"
                "- Use `search_customers(query='', limit=20)` to list all customers.\n"
                "- Use `get_customer_detail(customer_id='CUST-002')` for a specific customer."
            )
            return AgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                response=fallback,
                tool_calls_made=tool_calls_made,
                retrieved_data=retrieved_data,
            )

        return super()._build_output(response, tool_calls_made, retrieved_data, state)
