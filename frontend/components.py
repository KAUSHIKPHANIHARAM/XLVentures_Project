"""
frontend/components.py

Reusable Streamlit UI components for the Decision Intelligence Platform.

All functions are pure render functions — they read from their arguments
and st.session_state only through the UIState accessors. No side effects.
"""

from __future__ import annotations

import streamlit as st


def render_header(platform_name: str, domain: str) -> None:
    """Top-of-page header with platform name + active domain badge."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f"<h1 style='margin-bottom:0'>🧠 {platform_name}</h1>",
            unsafe_allow_html=True,
        )
        st.caption("Enterprise Reusable Agentic Decision Intelligence Platform")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if domain:
            st.success(f"Domain: **{domain.replace('_', ' ').title()}**")
    st.divider()


def render_query_input(placeholder: str = "Ask a question...") -> str | None:
    """
    Query input area with Submit button.

    Returns:
        The submitted query string, or None if not yet submitted.
    """
    with st.form(key="query_form", clear_on_submit=True):
        query = st.text_area(
            label="Your question",
            placeholder=placeholder,
            height=100,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "🔍  Analyze",
            use_container_width=True,
            type="primary",
        )
    return query.strip() if submitted and query.strip() else None


def render_running_indicator() -> None:
    """Animated spinner shown while the workflow is executing."""
    st.info("⏳ Workflow running — agents are thinking...", icon="🤖")


def render_error(message: str) -> None:
    """Display an error banner."""
    st.error(f"❌ **Error:** {message}")


def render_agent_trace(execution_trace: list[dict]) -> None:
    """
    Expandable agent execution timeline.

    Args:
        execution_trace: List of dicts from WorkflowState["execution_trace"].
    """
    if not execution_trace:
        return
    with st.expander("🔎 Agent Execution Trace", expanded=False):
        for step in execution_trace:
            agent = step.get("agent", "unknown")
            status = step.get("status", "")
            ts = step.get("timestamp", "")[:19].replace("T", " ")
            icon = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
            st.markdown(f"`{ts}` {icon} **{agent}** — {status}")


def render_risk_flags(risk_flags: list[dict]) -> None:
    """
    Risk flag badges. Each flag dict: {level, description, mitigation}.

    Args:
        risk_flags: From formatter.to_summary_dict()["risk_flags"].
    """
    if not risk_flags:
        return
    _LEVEL_COLOR = {
        "CRITICAL": "red",
        "HIGH": "orange",
        "MEDIUM": "blue",
        "LOW": "green",
    }
    st.markdown("#### ⚠️ Risk Flags")
    for flag in risk_flags:
        level = flag.get("level", "")
        desc = flag.get("description", "")
        mitigation = flag.get("mitigation", "")
        color = _LEVEL_COLOR.get(level, "gray")
        st.markdown(
            f":{color}[**{level}**] {desc}  \n"
            f"*Mitigation: {mitigation}*"
        )


def render_recommendations(recommendations: list[dict]) -> None:
    """
    Recommendation cards.

    Args:
        recommendations: From formatter.to_summary_dict()["recommendations"].
    """
    if not recommendations:
        st.info("No specific recommendations generated.")
        return

    st.markdown("#### 💡 Recommendations")
    for i, rec in enumerate(recommendations, 1):
        action = rec.get("action", "")
        priority = rec.get("priority", "MEDIUM")
        conf = rec.get("confidence_score", 0)
        sensitivity = rec.get("time_sensitivity", "standard")
        rationale = rec.get("rationale", "")

        _PRIORITY_ICON = {"HIGH": "⚡", "MEDIUM": "📌", "LOW": "📋"}
        icon = _PRIORITY_ICON.get(priority, "📋")

        with st.container(border=True):
            col1, col2, col3 = st.columns([6, 2, 2])
            with col1:
                st.markdown(f"**{icon} {i}. {action}**")
            with col2:
                st.metric("Confidence", f"{conf:.0%}")
            with col3:
                badge = "🔴 Urgent" if sensitivity == "immediate" else "🟡 Standard"
                st.markdown(f"<br>{badge}", unsafe_allow_html=True)
            if rationale:
                st.caption(rationale[:200])


def render_evidence_count(count: int) -> None:
    """Small metric showing how many evidence pieces were collected."""
    st.metric(label="Evidence Items", value=count, delta=None)


def render_metrics_row(summary: dict) -> None:
    """
    4-metric summary bar (confidence, risk, recommendations, evidence).

    Args:
        summary: From DecisionFormatter.to_summary_dict().
    """
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        conf = summary.get("confidence", 0)
        st.metric("Confidence", f"{conf:.0%}")
    with col2:
        risk = summary.get("overall_risk", "NONE")
        _RISK_DELTA = {"CRITICAL": -3, "HIGH": -2, "MEDIUM": -1, "LOW": 0, "NONE": 1}
        st.metric("Risk Level", risk, delta=_RISK_DELTA.get(risk, 0),
                  delta_color="inverse")
    with col3:
        n_recs = len(summary.get("recommendations", []))
        st.metric("Recommendations", n_recs)
    with col4:
        n_ev = summary.get("evidence_count", 0)
        st.metric("Evidence Items", n_ev)


def render_history_sidebar(history: list[dict]) -> str | None:
    """
    Sidebar panel showing recent query history.

    Returns:
        The query the user clicked (to re-load), or None.
    """
    if not history:
        st.sidebar.info("No history yet.")
        return None

    st.sidebar.markdown("### 📜 Recent Queries")
    selected = None
    for entry in history[:10]:
        q = entry.get("query", "")
        ts = entry.get("timestamp", "")
        risk = entry.get("result", {}).get("overall_risk", "")
        label = f"{q[:40]}{'...' if len(q) > 40 else ''}"
        if st.sidebar.button(label, key=f"hist_{ts}", help=f"Risk: {risk} | {ts}"):
            selected = q
    return selected


def render_knowledge_chunks(chunks: list[dict]) -> None:
    """
    Expandable panel showing pre-fetched knowledge chunks.

    Args:
        chunks: List of {content, source, similarity} dicts.
    """
    if not chunks:
        return
    with st.expander(f"📚 Knowledge Context ({len(chunks)} chunks)", expanded=False):
        for chunk in chunks:
            st.markdown(
                f"**{chunk.get('source', 'knowledge_base')}** "
                f"*(similarity: {chunk.get('similarity', 0):.0%})*"
            )
            st.caption(chunk.get("content", "")[:300])
            st.divider()
