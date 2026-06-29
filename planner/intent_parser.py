"""
planner/intent_parser.py

IntentParser — extracts intent and named entities from a raw user query.

Strategy:
    1. If RouterAgent has already run, read its JSON decision from WorkflowState
       (target_agent, intent, routing_confidence) — zero extra LLM cost.
    2. If not yet available, fall back to keyword heuristics.
    3. Named entity extraction (IDs, segments, risk levels) via regex — no NER model.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from config.schemas import DomainConfig
from schemas.query import IntentResult
from utils.logging import get_logger

logger = get_logger(__name__)

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "churn_analysis": ["churn", "risk", "at risk", "leaving", "cancel"],
    "customer_lookup": ["find", "search", "look up", "show me", "who is", "details", "profile"],
    "sentiment_analysis": ["sentiment", "feeling", "satisfaction", "happy", "unhappy", "feedback"],
    "interaction_history": ["history", "interactions", "past", "previous", "calls", "tickets"],
    "decision_recommendation": ["recommend", "what should", "action", "next step", "advice"],
    "knowledge_query": ["policy", "policies", "procedure", "how do we", "guideline", "best practice"],
    "list_customers": ["all customers", "list customers", "high risk", "premium customers", "by segment"],
}


class IntentParser:
    """
    Extracts a structured IntentResult from a user query.

    Reads RouterAgent output from WorkflowState first; falls back to heuristics.
    """

    def __init__(self, domain_config: DomainConfig) -> None:
        self._domain = domain_config.name

    def parse(
        self,
        query: str,
        workflow_state: dict[str, Any] | None = None,
    ) -> IntentResult:
        """
        Parse user intent from query + optional workflow state.

        Args:
            query:          Raw user query string.
            workflow_state: Current WorkflowState dict (may contain router output).

        Returns:
            IntentResult with intent label, confidence, and extracted entities.
        """
        if workflow_state:
            target_agent = workflow_state.get("target_agent", "")
            intent = workflow_state.get("intent", "")
            confidence = float(workflow_state.get("routing_confidence", 0.0))
            reasoning = workflow_state.get("routing_reasoning", "")

            if target_agent and confidence > 0.5:
                entities = self._extract_entities(query)
                logger.debug(
                    "Intent from router: '%s' -> target='%s' confidence=%.2f",
                    intent, target_agent, confidence,
                )
                requires_multi = self._requires_multi_agent(intent)
                return IntentResult(
                    query_id=str(uuid.uuid4()),
                    intent=intent or self._agent_to_intent(target_agent),
                    query_type=self._intent_to_query_type(intent),
                    target_agent=target_agent,
                    confidence=confidence,
                    reasoning=reasoning,
                    extracted_entities=entities,
                    requires_multi_agent=requires_multi,
                )

        return self._heuristic_parse(query)

    def _heuristic_parse(self, query: str) -> IntentResult:
        """Simple keyword-based intent classification fallback."""
        query_lower = query.lower()
        best_intent = "customer_lookup"
        best_score = 0

        for intent, keywords in _INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_intent = intent

        target_agent = self._intent_to_agent(best_intent)
        confidence = min(0.5 + best_score * 0.15, 0.9)
        entities = self._extract_entities(query)

        logger.debug("Heuristic intent: '%s' confidence=%.2f entities=%s",
                     best_intent, confidence, entities)

        return IntentResult(
            query_id=str(uuid.uuid4()),
            intent=best_intent,
            query_type=self._intent_to_query_type(best_intent),
            target_agent=target_agent,
            confidence=confidence,
            reasoning=f"Keyword heuristic matched intent '{best_intent}'.",
            extracted_entities=entities,
            requires_multi_agent=self._requires_multi_agent(best_intent),
        )

    def _extract_entities(self, query: str) -> dict[str, Any]:
        """Extract named entities (IDs, segments, risk levels) from the query."""
        entities: dict[str, Any] = {}

        id_match = re.search(r"\b(?:customer\s+|id\s+|#)?(CUST[- ]?\d{1,5}|\d{1,5})\b", query, re.IGNORECASE)
        if id_match:
            id_text = id_match.group(1)
            if id_text.upper().startswith("CUST"):
                entities["customer_id"] = id_text.upper().replace(" ", "-")
            else:
                entities["customer_id"] = int(id_text)
        elif not entities:
            nums = re.findall(r"\b(\d{1,5})\b", query)
            if nums and len(nums) == 1:
                entities["customer_id"] = int(nums[0])

        for seg in ("premium", "standard", "trial"):
            if seg in query.lower():
                entities["segment"] = seg.capitalize()
                break

        for risk in ("high", "medium", "low"):
            if f"{risk} risk" in query.lower() or f"{risk} churn" in query.lower():
                entities["risk_level"] = risk.upper()
                break

        return entities

    @staticmethod
    def _requires_multi_agent(intent: str) -> bool:
        return intent in ("churn_analysis", "decision_recommendation", "sentiment_analysis")

    @staticmethod
    def _agent_to_intent(target_agent: str) -> str:
        return {
            "data_agent": "customer_lookup",
            "analysis_agent": "churn_analysis",
            "decision_agent": "decision_recommendation",
            "knowledge_agent": "knowledge_query",
        }.get(target_agent, "customer_lookup")

    @staticmethod
    def _intent_to_agent(intent: str) -> str:
        return {
            "churn_analysis": "analysis_agent",
            "sentiment_analysis": "analysis_agent",
            "decision_recommendation": "decision_agent",
            "knowledge_query": "knowledge_agent",
        }.get(intent, "data_agent")

    @staticmethod
    def _intent_to_query_type(intent: str) -> str:
        return {
            "churn_analysis": "analysis",
            "sentiment_analysis": "analysis",
            "decision_recommendation": "decision",
            "knowledge_query": "knowledge",
            "list_customers": "list",
        }.get(intent, "lookup")
