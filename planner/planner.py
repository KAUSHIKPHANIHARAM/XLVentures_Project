"""
planner/planner.py

Planner — single entry point for query planning and initial state creation.

Combines IntentParser + PlanBuilder. Called by the workflow orchestrator
before LangGraph execution begins.
"""

from __future__ import annotations

import uuid
from typing import Any

from config.schemas import DomainConfig
from planner.intent_parser import IntentParser
from planner.plan_builder import PlanBuilder
from schemas.agent import WorkflowState
from schemas.query import PlannerOutput
from utils.datetime_utils import utc_now_iso
from utils.logging import get_logger

logger = get_logger(__name__)


class Planner:
    """
    Main planner — maps a user query to an ordered agent execution plan.

    Args:
        domain_config: Domain configuration for this planner instance.
    """

    def __init__(self, domain_config: DomainConfig) -> None:
        self._domain = domain_config.name
        self._intent_parser = IntentParser(domain_config)
        self._plan_builder = PlanBuilder(domain_config)

    def plan(
        self,
        query: str,
        workflow_state: WorkflowState | None = None,
    ) -> PlannerOutput:
        """
        Generate an execution plan for a user query.

        Args:
            query:          Raw user query.
            workflow_state: Current state (may contain router output for refinement).

        Returns:
            PlannerOutput describing the ordered agent sequence.
        """
        logger.info("Planning for query: '%.80s'", query)
        state_dict: dict[str, Any] = dict(workflow_state) if workflow_state else {}
        intent_result = self._intent_parser.parse(query, state_dict)
        plan = self._plan_builder.build(intent_result)
        logger.info(
            "Plan ready: %d steps | intent='%s' | complexity=%s",
            len(plan.steps), plan.intent, plan.estimated_complexity,
        )
        return plan

    def initial_state(self, query: str, session_id: str) -> WorkflowState:
        """
        Build the initial WorkflowState for a new query.

        Called before the LangGraph graph starts execution.

        Args:
            query:      Raw user query.
            session_id: Unique session identifier.

        Returns:
            A fully initialized WorkflowState.
        """
        return WorkflowState(
            run_id=str(uuid.uuid4()),
            domain=self._domain,
            session_id=session_id,
            user_query=query,
            metadata={},
            intent="",
            target_agent="",
            routing_confidence=0.0,
            routing_reasoning="",
            retrieved_data=[],
            knowledge_chunks=[],
            memory_entries=[],
            agent_outputs={},
            final_response="",
            workflow_status="pending",
            error=None,
            execution_trace=[],
            total_tool_calls=0,
            started_at=utc_now_iso(),
            completed_at="",
        )
