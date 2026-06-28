"""
planner/plan_builder.py

PlanBuilder — converts an IntentResult into an ordered execution plan.

Reads the WorkflowConfig from the domain YAML (nodes, edges, entry_point,
terminal_node) and produces a PlannerOutput with ordered PlanSteps.

Graph pattern (from customer_management.yaml):
    entry_point (router_agent)
      -> [conditional edge on target_agent]
        -> specialist_agent (data/analysis/decision/knowledge)
          -> terminal_node (synthesizer_agent)

Multi-hop intents (churn_analysis, decision_recommendation) chain
data_agent -> analysis_agent -> decision_agent before synthesizer.
"""

from __future__ import annotations

import uuid

from config.schemas import DomainConfig, WorkflowConfig
from schemas.query import IntentResult, PlanStep, PlannerOutput
from utils.logging import get_logger

logger = get_logger(__name__)

# Intents that require a specific specialist chain before synthesizer
_MULTI_HOP_INTENTS: dict[str, list[str]] = {
    "churn_analysis": ["data_agent", "analysis_agent"],
    "sentiment_analysis": ["data_agent", "analysis_agent"],
    "decision_recommendation": ["data_agent", "analysis_agent", "decision_agent"],
    "interaction_history": ["data_agent"],
    "customer_lookup": ["data_agent"],
    "list_customers": ["data_agent"],
    "knowledge_query": ["knowledge_agent"],
}


class PlanBuilder:
    """
    Builds a PlannerOutput from an IntentResult using workflow graph config.

    Args:
        domain_config: Domain configuration with workflow graph definitions.
    """

    def __init__(self, domain_config: DomainConfig) -> None:
        self._domain = domain_config.name
        self._domain_config = domain_config
        self._workflow = self._get_primary_workflow()

    def build(self, intent_result: IntentResult) -> PlannerOutput:
        """
        Build the execution plan for the detected intent.

        Args:
            intent_result: Parsed intent with target_agent and confidence.

        Returns:
            PlannerOutput with ordered PlanStep list.
        """
        steps = self._build_steps(intent_result)
        num_specialists = len(steps) - 2  # minus router + synthesizer
        complexity = (
            "high" if num_specialists >= 3
            else "medium" if num_specialists == 2
            else "low"
        )

        plan = PlannerOutput(
            query_id=intent_result.query_id,
            domain=self._domain,
            intent=intent_result,           # IntentResult object, not a string
            steps=steps,
            estimated_complexity=complexity,
            reasoning=(
                f"Detected intent '{intent_result.intent}' with confidence "
                f"{intent_result.confidence:.0%}. "
                f"Executing {len(steps)}-step workflow via "
                f"{self._workflow.name if self._workflow else 'default'}."
            ),
        )

        logger.info(
            "Plan built: intent='%s' steps=%s complexity=%s",
            intent_result.intent,
            [s.agent_name for s in steps],
            complexity,
        )
        return plan

    def _build_steps(self, intent_result: IntentResult) -> list[PlanStep]:
        """Build the ordered PlanStep list from intent."""
        steps: list[PlanStep] = []

        entry = self._workflow.entry_point if self._workflow else "router_agent"
        terminal = self._workflow.terminal_node if self._workflow else "synthesizer_agent"

        # Step 0: Router (entry point — always first)
        steps.append(PlanStep(
            step_index=0,
            agent_name=entry,
            description="Classify intent and route to the appropriate specialist agent.",
            depends_on=[],
            input_keys=["user_query"],
            output_keys=["intent", "target_agent", "routing_confidence"],
        ))

        # Steps 1+: Specialist chain based on intent
        specialists = self._resolve_specialists(intent_result)
        for i, agent_name in enumerate(specialists):
            steps.append(PlanStep(
                step_index=i + 1,
                agent_name=agent_name,
                description=self._agent_description(agent_name),
                depends_on=[i],  # depends on the previous step by index
                input_keys=["user_query", "retrieved_data", "knowledge_chunks"],
                output_keys=["retrieved_data", "agent_outputs"],
            ))

        # Final: Synthesizer (terminal — always last)
        last_idx = len(steps) - 1
        steps.append(PlanStep(
            step_index=len(steps),
            agent_name=terminal,
            description="Synthesise all specialist outputs into a coherent final response.",
            depends_on=[last_idx],  # depends on the last specialist step
            input_keys=["agent_outputs", "retrieved_data"],
            output_keys=["final_response", "workflow_status"],
        ))


        return steps

    def _resolve_specialists(self, intent_result: IntentResult) -> list[str]:
        """Determine the specialist agent sequence for this intent."""
        intent = intent_result.intent

        # Use intent-based multi-hop sequence
        sequence = list(_MULTI_HOP_INTENTS.get(intent, []))

        # Override with router's target if not already covered
        if intent_result.target_agent and intent_result.target_agent not in sequence:
            sequence = [intent_result.target_agent]

        if not sequence:
            sequence = ["data_agent"]

        # Validate against workflow nodes
        if self._workflow:
            valid = set(self._workflow.nodes)
            sequence = [a for a in sequence if a in valid]

        return sequence or ["data_agent"]

    def _get_primary_workflow(self) -> WorkflowConfig | None:
        if not self._domain_config.workflows:
            logger.warning("Domain '%s' has no workflow definitions.", self._domain)
            return None
        return self._domain_config.workflows[0]

    @staticmethod
    def _agent_description(agent_name: str) -> str:
        return {
            "data_agent": "Retrieve relevant entity records from the data store.",
            "analysis_agent": "Analyse churn risk, sentiment, and behavioural patterns.",
            "decision_agent": "Generate actionable recommendations grounded in data.",
            "knowledge_agent": "Search domain knowledge base for policies and guidelines.",
        }.get(agent_name, f"Execute {agent_name}.")
