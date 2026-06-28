"""
decision/engine.py

DecisionEngine — assembles a structured DecisionResult from WorkflowState.

Schema reality (verified):
    - DecisionResult has NO top-level risk_flags or evidence fields.
    - Both risk_flags (list[RiskFlag]) and evidence (list[Evidence]) live
      on each Recommendation object.
    - overall_risk on DecisionResult is the highest-severity flag across all recs.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from schemas.agent import AgentOutput, AgentStatus, WorkflowState
from schemas.decision import (
    DecisionResult,
    Evidence,
    Recommendation,
    RiskFlag,
)
from utils.datetime_utils import utc_now_iso
from utils.logging import get_logger

logger = get_logger(__name__)

# (regex_pattern, flag_type, level)  — level must match RiskLevel enum (lowercase)
_RISK_PATTERNS: list[tuple[str, str, str]] = [
    (r"churn risk.{0,30}(high|critical|0\.[789]\d)", "high_churn_risk", "high"),
    (r"(angry|hostile|threat|legal|lawsuit|terminate contract)", "escalation_required", "critical"),
    (r"(billing dispute|overcharg|incorrect invoice)", "billing_issue", "medium"),
    (r"(sla breach|sla violation|downtime|outage)", "sla_violation", "high"),
    (r"(no response|unresponsive|ghosting)", "engagement_gap", "medium"),
    (r"(competitor|switching|alternative|looking at salesforce|looking at hubspot)", "competitive_threat", "high"),
]

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}


class DecisionEngine:
    """
    Assembles agent outputs into a structured, explainable DecisionResult.

    Args:
        domain: Domain name for metadata attribution.
    """

    def __init__(self, domain: str) -> None:
        self._domain = domain

    def assemble(self, state: WorkflowState) -> DecisionResult:
        """Build a DecisionResult from a completed WorkflowState."""
        agent_outputs: dict[str, AgentOutput] = state.get("agent_outputs", {})
        final_response: str = state.get("final_response", "")
        user_query: str = state.get("user_query", "")
        retrieved_data: list[dict] = state.get("retrieved_data", [])
        intent: str = state.get("intent", "")

        # Detect risk flags from all agent text
        risk_flags = self._detect_risk_flags(agent_outputs, final_response)

        # Extract evidence items
        evidence_items = self._extract_evidence(agent_outputs, retrieved_data)

        # Build recommendations, attaching relevant risk_flags + evidence to each
        recommendations = self._build_recommendations(
            agent_outputs, final_response, retrieved_data,
            risk_flags=risk_flags, evidence=evidence_items,
        )

        agents_used = [
            name for name, out in agent_outputs.items()
            if out.status == AgentStatus.COMPLETED
        ]

        # Overall confidence: average of non-zero agent confidences
        confidences = [
            out.confidence for out in agent_outputs.values()
            if out.confidence and out.confidence > 0
        ]
        overall_confidence = (
            round(sum(confidences) / len(confidences), 3) if confidences else 0.75
        )

        # overall_risk = highest severity across all recommendation risk_flags
        overall_risk = "none"
        for rec in recommendations:
            for flag in (rec.risk_flags or []):
                level = flag.level if isinstance(flag.level, str) else flag.level.value
                if _SEVERITY_ORDER.get(level, 0) > _SEVERITY_ORDER.get(overall_risk, 0):
                    overall_risk = level

        summary = self._build_summary(
            intent, final_response, recommendations, risk_flags, agents_used
        )

        result = DecisionResult(
            result_id=str(uuid.uuid4()),
            request_id=state.get("run_id", str(uuid.uuid4())),
            domain=self._domain,
            entity_type=self._infer_entity_type(retrieved_data),
            entity_id=self._infer_entity_id(retrieved_data),
            status="advisory",
            overall_risk=overall_risk,
            summary=summary,
            recommendations=recommendations,
            alternative_options=[],
            requires_human_review=any(
                (f.level if isinstance(f.level, str) else f.level.value) == "critical"
                for rec in recommendations for f in (rec.risk_flags or [])
            ),
            reasoning_chain=self._build_reasoning_chain(agent_outputs),
            metadata={
                "intent": intent,
                "agents_used": agents_used,
                "data_sources": self._collect_data_sources(agent_outputs, retrieved_data),
                "overall_confidence": overall_confidence,
                "risk_flag_count": len(risk_flags),
                "evidence_count": len(evidence_items),
                "execution_trace": state.get("execution_trace", []),
                "query": user_query,
                "session_id": state.get("session_id", ""),
                "final_response": final_response,
            },
        )

        logger.info(
            "DecisionResult assembled: %d recommendations, %d risk flags, "
            "risk=%s, agents=%s",
            len(recommendations), len(risk_flags), overall_risk, agents_used,
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_recommendations(
        self,
        agent_outputs: dict[str, AgentOutput],
        final_response: str,
        retrieved_data: list[dict],
        risk_flags: list[RiskFlag],
        evidence: list[Evidence],
    ) -> list[Recommendation]:
        """Build Recommendation objects with risk_flags and evidence attached."""
        recs: list[Recommendation] = []

        # Primary: decision_agent output
        decision_out = agent_outputs.get("decision_agent")
        if decision_out and decision_out.status == AgentStatus.COMPLETED:
            recs.append(Recommendation(
                recommendation_id=str(uuid.uuid4()),
                action=self._extract_action(decision_out.response),
                rationale=decision_out.response[:600],
                confidence_level=self._score_to_level(decision_out.confidence or 0.8),
                confidence_score=decision_out.confidence or 0.8,
                priority=1,
                evidence=evidence[:3],        # attach evidence to primary rec
                risk_flags=risk_flags[:3],    # attach risk flags to primary rec
                estimated_impact="Potential to prevent customer churn and protect revenue.",
                time_sensitivity="immediate",
                metadata={"source_agent": "decision_agent"},
            ))

        # Secondary: generate_decision_recommendation tool result
        for item in retrieved_data:
            if item.get("tool") == "generate_decision_recommendation":
                result = item.get("result", {})
                if isinstance(result, dict) and "recommended_action" in result:
                    score = float(result.get("confidence", 0.75))
                    risk = result.get("risk_level", "MEDIUM")
                    priority_int = 1 if risk == "HIGH" else 2 if risk == "MEDIUM" else 3
                    recs.append(Recommendation(
                        recommendation_id=str(uuid.uuid4()),
                        action=result["recommended_action"],
                        rationale=result.get("rationale", "")[:400],
                        confidence_level=self._score_to_level(score),
                        confidence_score=score,
                        priority=priority_int,
                        evidence=[],
                        risk_flags=[],
                        estimated_impact="",
                        time_sensitivity="immediate" if risk == "HIGH" else "standard",
                        metadata={"source": "tool:generate_decision_recommendation"},
                    ))

        # Fallback: synthesizer/final response
        if not recs and final_response:
            recs.append(Recommendation(
                recommendation_id=str(uuid.uuid4()),
                action=self._extract_action(final_response),
                rationale=final_response[:400],
                confidence_level="medium",
                confidence_score=0.7,
                priority=2,
                evidence=evidence[:2],
                risk_flags=risk_flags[:2],
                estimated_impact="",
                time_sensitivity="standard",
                metadata={"source_agent": "synthesizer_agent"},
            ))

        # Deduplicate
        seen: dict[str, Recommendation] = {}
        for rec in recs:
            key = rec.action[:60]
            if key not in seen or rec.confidence_score > seen[key].confidence_score:
                seen[key] = rec
        return list(seen.values())[:3]

    def _extract_evidence(
        self,
        agent_outputs: dict[str, AgentOutput],
        retrieved_data: list[dict],
    ) -> list[Evidence]:
        evidence: list[Evidence] = []

        for item in retrieved_data:
            tool = item.get("tool", "")
            result = item.get("result", {})

            if tool == "analyze_churn_risk" and isinstance(result, dict):
                evidence.append(Evidence(
                    source=tool,
                    description=result.get("analysis", "")[:300],
                    data=result,
                    weight=0.9,
                ))
            elif tool == "get_interaction_history" and isinstance(result, dict):
                interactions = result.get("interactions", [])
                neg = sum(1 for i in interactions if i.get("sentiment") == "negative")
                total = result.get("total_interactions", len(interactions))
                evidence.append(Evidence(
                    source=tool,
                    description=(
                        f"{total} interactions, {neg} negative. "
                        + "; ".join(i.get("subject", "")[:40] for i in interactions[:2])
                    )[:300],
                    data={"total": total, "negative": neg},
                    weight=0.85,
                ))
            elif tool == "get_customer_detail" and isinstance(result, dict):
                customer = result.get("customer", {})
                evidence.append(Evidence(
                    source=tool,
                    description=(
                        f"Customer: {result.get('display_name', '')} | "
                        f"Segment: {customer.get('segment')} | "
                        f"LTV: ${customer.get('lifetime_value', 0):,.0f} | "
                        f"Churn: {customer.get('churn_risk_score', 'N/A')}"
                    )[:300],
                    data=customer,
                    weight=1.0,
                ))

        analysis_out = agent_outputs.get("analysis_agent")
        if analysis_out and analysis_out.status == AgentStatus.COMPLETED:
            evidence.append(Evidence(
                source="analysis_agent",
                description=analysis_out.response[:300],
                data={},
                weight=analysis_out.confidence or 0.8,
            ))

        return evidence[:5]

    def _detect_risk_flags(
        self,
        agent_outputs: dict[str, AgentOutput],
        final_response: str,
    ) -> list[RiskFlag]:
        all_text = final_response
        for output in agent_outputs.values():
            if output.response:
                all_text += " " + output.response
        all_text_lower = all_text.lower()

        flags: list[RiskFlag] = []
        seen: set[str] = set()
        for pattern, flag_type, level in _RISK_PATTERNS:
            if flag_type in seen:
                continue
            if re.search(pattern, all_text_lower):
                flags.append(RiskFlag(
                    level=level,
                    description=self._risk_description(flag_type),
                    mitigation=self._risk_mitigation(flag_type),
                ))
                seen.add(flag_type)
        return flags

    def _collect_data_sources(
        self,
        agent_outputs: dict[str, AgentOutput],
        retrieved_data: list[dict],
    ) -> list[str]:
        sources: set[str] = set()
        for item in retrieved_data:
            if item.get("tool"):
                sources.add(item["tool"])
        for output in agent_outputs.values():
            for tool_name in output.tool_calls_made:
                sources.add(tool_name)
        return sorted(sources)

    def _build_summary(
        self, intent: str, final_response: str,
        recs: list[Recommendation], flags: list[RiskFlag], agents: list[str],
    ) -> str:
        parts = []
        if final_response:
            parts.append(final_response[:400])
        if recs:
            parts.append(f"Top recommendation: {recs[0].action[:100]}")
        if flags:
            parts.append(f"Risk flags: {', '.join(f.level for f in flags)}")
        parts.append(f"Agents: {', '.join(agents)}.")
        return " | ".join(parts)

    def _build_reasoning_chain(
        self, agent_outputs: dict[str, AgentOutput]
    ) -> list[str]:
        chain = []
        for name, output in agent_outputs.items():
            if output.status == AgentStatus.COMPLETED and output.reasoning:
                chain.append(f"[{name}] {output.reasoning[:200]}")
        return chain

    @staticmethod
    def _infer_entity_type(retrieved_data: list[dict]) -> str:
        for item in retrieved_data:
            result = item.get("result", {})
            if isinstance(result, dict) and "customer" in result:
                return "Customer"
        return ""

    @staticmethod
    def _infer_entity_id(retrieved_data: list[dict]) -> str:
        for item in retrieved_data:
            result = item.get("result", {})
            if isinstance(result, dict):
                cid = result.get("customer_id") or result.get("entity_id")
                if cid:
                    return str(cid)
        return ""

    @staticmethod
    def _extract_action(text: str) -> str:
        patterns = [
            r"(?:recommend|suggest|should|must|action[:\s]+)([^.!?\n]{20,150})",
            r"(?:immediately|urgently|priority)[:\s]+([^.!?\n]{20,150})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        first = re.split(r"[.!?\n]", text.strip())[0]
        return first[:200].strip()

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.70:
            return "high"
        if score >= 0.45:
            return "medium"
        return "low"

    @staticmethod
    def _risk_description(flag_type: str) -> str:
        return {
            "high_churn_risk": "Customer has elevated churn risk score requiring immediate attention.",
            "escalation_required": "Situation requires senior escalation — potential contract loss.",
            "billing_issue": "Billing dispute identified. Requires finance/CS review.",
            "sla_violation": "SLA breach detected. Review compensation and remediation.",
            "engagement_gap": "Customer not responding — risk of silent churn.",
            "competitive_threat": "Customer evaluating competitors. Retain immediately.",
        }.get(flag_type, f"Risk: {flag_type}")

    @staticmethod
    def _risk_mitigation(flag_type: str) -> str:
        return {
            "high_churn_risk": "Schedule retention call within 48 hours with a senior CSM.",
            "escalation_required": "Escalate to VP Customer Success within 24 hours.",
            "billing_issue": "Issue credit note and schedule clarification call.",
            "sla_violation": "Apply SLA credit per contract; provide incident post-mortem.",
            "engagement_gap": "Send re-engagement email; follow up by phone if no response in 72h.",
            "competitive_threat": "Schedule executive-level call; prepare competitive battle card.",
        }.get(flag_type, "Review and take appropriate action.")
