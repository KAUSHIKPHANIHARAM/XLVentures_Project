"""
decision/formatter.py

DecisionFormatter — formats a DecisionResult for Streamlit display and API responses.

Schema note: risk_flags and evidence live on Recommendation objects, not DecisionResult.
We collect them from all recommendations for display.
"""

from __future__ import annotations

from schemas.decision import DecisionResult, Evidence, Recommendation, RiskFlag
from utils.json_utils import safe_json_dumps

_LEVEL_ICON: dict[str, str] = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
    "none":     "⚪",
}


def _level_str(level: Any) -> str:
    """Safely convert a RiskLevel enum or string to lowercase string."""
    return level.value if hasattr(level, "value") else str(level).lower()


def _priority_icon(p: int) -> str:
    return "⚡" if p == 1 else "📌" if p == 2 else "📋"


class DecisionFormatter:
    """Formats DecisionResult objects for various presentation contexts."""

    @staticmethod
    def to_markdown(result: DecisionResult) -> str:
        """Produce a rich markdown string for Streamlit display."""
        from typing import Any  # local import for _level_str helper
        meta = result.metadata or {}
        query = meta.get("query", "")
        agents_used = meta.get("agents_used", [])
        data_sources = meta.get("data_sources", [])
        final_response = meta.get("final_response", result.summary or "")
        confidence = meta.get("overall_confidence", 0.75)
        risk_flag_count = meta.get("risk_flag_count", 0)

        # Collect all risk flags and evidence from recommendations
        all_flags: list[RiskFlag] = []
        all_evidence: list[Evidence] = []
        for rec in result.recommendations:
            all_flags.extend(rec.risk_flags or [])
            all_evidence.extend(rec.evidence or [])

        overall_risk_str = (
            result.overall_risk.value
            if hasattr(result.overall_risk, "value")
            else str(result.overall_risk)
        )

        lines: list[str] = []
        lines.append("## Decision Intelligence Report")
        if query:
            lines.append(f"**Query:** {query}")
        risk_icon = _LEVEL_ICON.get(overall_risk_str.lower(), "⚪")
        lines.append(
            f"**Confidence:** {confidence:.0%} | "
            f"**Risk:** {risk_icon} {overall_risk_str.upper()} | "
            f"**Domain:** {result.domain}"
        )
        if result.requires_human_review:
            lines.append("> ⚠️ **Human review recommended** for this decision.")
        lines.append("")

        if final_response:
            lines.append("### Answer")
            lines.append(final_response)
            lines.append("")

        # Risk flags (from recommendations)
        if all_flags:
            lines.append("### Risk Flags")
            seen_descs: set[str] = set()
            for flag in all_flags:
                level = _level_str(flag.level)
                desc = flag.description
                if desc in seen_descs:
                    continue
                seen_descs.add(desc)
                icon = _LEVEL_ICON.get(level, "⚪")
                lines.append(f"{icon} **{level.upper()}** — {desc}")
                lines.append(f"  *Mitigation: {flag.mitigation}*")
            lines.append("")

        # Recommendations
        if result.recommendations:
            lines.append("### Recommendations")
            for i, rec in enumerate(result.recommendations, 1):
                icon = _priority_icon(rec.priority)
                pct = f"{rec.confidence_score:.0%}"
                lines.append(f"{icon} **{i}. {rec.action}** *(confidence: {pct})*")
                if rec.rationale:
                    lines.append(f"   > {rec.rationale[:250]}")
                if rec.time_sensitivity == "immediate":
                    lines.append("   > ⏱️ *Immediate action required*")
                lines.append("")

        # Evidence
        if all_evidence:
            lines.append("### Supporting Evidence")
            seen_evs: set[str] = set()
            for ev in all_evidence[:5]:
                if ev.description in seen_evs:
                    continue
                seen_evs.add(ev.description)
                lines.append(f"- **{ev.source}**: {ev.description[:200]}")
            lines.append("")

        # Execution summary
        lines.append("### Execution Summary")
        if agents_used:
            lines.append(f"- **Agents:** {', '.join(agents_used)}")
        if data_sources:
            lines.append(f"- **Data Sources:** {', '.join(data_sources)}")
        lines.append(f"- **Risk Flags Detected:** {risk_flag_count}")
        lines.append(f"- **Generated:** {result.created_at[:19].replace('T', ' ')} UTC")
        if result.reasoning_chain:
            lines.append("\n**Reasoning Chain:**")
            for step in result.reasoning_chain[:3]:
                lines.append(f"  - {step}")

        return "\n".join(lines)

    @staticmethod
    def to_summary_dict(result: DecisionResult) -> dict:
        """Compact dict for frontend components."""
        meta = result.metadata or {}
        overall_risk_str = (
            result.overall_risk.value
            if hasattr(result.overall_risk, "value")
            else str(result.overall_risk)
        )

        # Collect from recommendations
        all_flags: list[RiskFlag] = []
        all_evidence: list[Evidence] = []
        for rec in result.recommendations:
            all_flags.extend(rec.risk_flags or [])
            all_evidence.extend(rec.evidence or [])

        return {
            "query": meta.get("query", ""),
            "intent": meta.get("intent", ""),
            "confidence": meta.get("overall_confidence", 0.75),
            "final_response": meta.get("final_response", result.summary),
            "overall_risk": overall_risk_str.upper(),
            "requires_human_review": result.requires_human_review,
            "recommendations": [
                {
                    "action": r.action,
                    "priority": (
                        "HIGH" if r.priority == 1
                        else "MEDIUM" if r.priority == 2
                        else "LOW"
                    ),
                    "confidence_score": r.confidence_score,
                    "time_sensitivity": r.time_sensitivity,
                    "rationale": r.rationale[:200],
                }
                for r in result.recommendations
            ],
            "risk_flags": [
                {
                    "level": _level_str(f.level).upper(),
                    "description": f.description,
                    "mitigation": f.mitigation,
                }
                for f in all_flags
            ],
            "evidence_count": len(all_evidence),
            "agents_used": meta.get("agents_used", []),
            "data_sources": meta.get("data_sources", []),
            "created_at": result.created_at,
        }

    @staticmethod
    def to_json(result: DecisionResult, indent: int = 2) -> str:
        """Serialize the full DecisionResult to JSON."""
        return safe_json_dumps(result.model_dump(), indent=indent)

    @staticmethod
    def format_risk_badge(flag: RiskFlag) -> str:
        level = _level_str(flag.level)
        icon = _LEVEL_ICON.get(level, "⚪")
        return f"{icon} {level.upper()}: {flag.description[:60]}"


# module-level alias needed by formatter methods
from typing import Any  # noqa: E402 (after class definition for clarity)
