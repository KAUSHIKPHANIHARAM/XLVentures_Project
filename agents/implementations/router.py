"""
agents/implementations/router.py

RouterAgent — analyses user intent and routes to the correct specialist agent.

This is always the entry point of every workflow. It reads the user query,
classifies intent, and writes the target_agent name to WorkflowState.

The LLM is prompted to return a structured JSON routing decision.
No tools are bound to this agent.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from agents.base import BaseAgent
from schemas.agent import AgentOutput, AgentStatus, WorkflowState
from utils.json_utils import parse_llm_json
from utils.logging import get_logger

logger = get_logger(__name__)


class RouterAgent(BaseAgent):
    """Routes user queries to the correct specialist agent."""

    def _build_prompt(self, state: WorkflowState) -> list[BaseMessage]:
        user_query = state.get("user_query", "")
        return [
            self._system_message(),
            HumanMessage(content=f"User query: {user_query}"),
        ]

    def _state_updates(
        self, output: AgentOutput, state: WorkflowState
    ) -> dict[str, Any]:
        """Parse the routing JSON and write intent/target_agent to state."""
        parsed = parse_llm_json(output.response) or {}

        target_agent = parsed.get("target_agent", "data_agent")
        intent = parsed.get("intent", state.get("user_query", ""))
        confidence = float(parsed.get("confidence", 0.7))
        reasoning = parsed.get("reasoning", "")

        logger.info(
            "Router decision: target='%s' confidence=%.2f intent='%.60s'",
            target_agent,
            confidence,
            intent,
        )

        return {
            "intent": intent,
            "target_agent": target_agent,
            "routing_confidence": confidence,
            "routing_reasoning": reasoning,
        }

    def _build_output(
        self,
        response: str,
        tool_calls_made: list[str],
        retrieved_data: list[dict[str, Any]],
        state: WorkflowState,
    ) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            response=response,
            tool_calls_made=[],
            retrieved_data=[],
        )
