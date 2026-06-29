"""
frontend/components.py

Reusable Streamlit UI components for the Decision Intelligence Platform.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


def inject_dashboard_css() -> None:
    """Inject polished enterprise dashboard styling for Streamlit."""
    st.markdown(
        """
        <style>
            :root {
                --bg: #07111f;
                --panel: rgba(15, 23, 42, 0.92);
                --panel-soft: rgba(15, 23, 42, 0.75);
                --border: rgba(148, 163, 184, 0.22);
                --text: #e2e8f0;
                --muted: #94a3b8;
                --accent: #38bdf8;
                --accent-2: #818cf8;
                --good: #22c55e;
                --warn: #f59e0b;
                --danger: #ef4444;
            }
            .stApp {
                background: linear-gradient(135deg, #020617 0%, #0f172a 40%, #111827 100%);
                color: var(--text);
            }
            .block-container {
                padding-top: 0.8rem;
                padding-bottom: 2rem;
                max-width: 1500px;
            }
            .dashboard-card {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 18px;
                padding: 1rem 1.1rem;
                margin-bottom: 0.9rem;
                box-shadow: 0 10px 24px rgba(2, 8, 23, 0.28);
            }
            .hero-shell {
                background: linear-gradient(90deg, rgba(56, 189, 248, 0.16), rgba(129, 140, 248, 0.12));
                border: 1px solid var(--border);
                border-radius: 22px;
                padding: 1rem 1.2rem;
                margin-bottom: 1rem;
            }
            .hero-title {
                font-size: 1.75rem;
                font-weight: 700;
                letter-spacing: -0.02em;
            }
            .hero-subtitle {
                color: var(--muted);
                font-size: 0.95rem;
                margin-top: -0.2rem;
            }
            .pill {
                display: inline-block;
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid var(--border);
                border-radius: 999px;
                padding: 0.25rem 0.6rem;
                color: var(--text);
                font-size: 0.8rem;
                margin-right: 0.35rem;
                margin-top: 0.3rem;
            }
            .status-good { border-color: rgba(34, 197, 94, 0.4); color: #bbf7d0; }
            .status-warn { border-color: rgba(245, 158, 11, 0.4); color: #fde68a; }
            .status-danger { border-color: rgba(239, 68, 68, 0.4); color: #fecaca; }
            .metric-card {
                background: var(--panel-soft);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 0.85rem 0.95rem;
                min-height: 110px;
            }
            .metric-label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; }
            .metric-value { font-size: 1.25rem; font-weight: 700; margin-top: 0.3rem; }
            .metric-sub { color: var(--muted); font-size: 0.85rem; margin-top: 0.3rem; }
            .sidebar .sidebar-content {
                background: linear-gradient(180deg, #020617 0%, #111827 100%);
            }
            .st-emotion-cache-1y4p8pa { padding: 1rem 1rem 1.5rem 1rem; }
            .stButton>button {
                border-radius: 10px;
                border: 1px solid rgba(148,163,184,0.18);
                background: rgba(15,23,42,0.9);
                color: var(--text);
            }
            .stButton>button:hover {
                border-color: rgba(56,189,248,0.45);
                background: rgba(15,23,42,1);
            }
            [data-testid="stMetricValue"] { font-size: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalize_value(value: Any, fallback: str = "Not available") -> str:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        if 0.0 <= value <= 1.0 and isinstance(value, float):
            return f"{value:.0%}"
        return str(value)
    if isinstance(value, str):
        return value.strip() or fallback
    return str(value)


def _format_timestamp(value: Any) -> str:
    if not value:
        return "Not recorded"
    text = str(value)
    if "T" in text:
        text = text.replace("T", " ")
    return text[:19]


def render_header(
    platform_name: str,
    domain: str | None = None,
    current_customer: str | None = None,
    workflow: str | None = None,
    session_status: str | None = None,
    health: str | None = None,
    timestamp: str | None = None,
    subtitle: str | None = None,
) -> None:
    """Render a clean, business-friendly page header."""
    inject_dashboard_css()
    st.markdown("<div class='hero-shell'>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-title'>{platform_name}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='hero-subtitle'>{subtitle or 'AI-powered Customer Success Decision Support'}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_query_input(default_value: str = "", placeholder: str = "e.g. CUST-002, Acme Corp, Jane Smith, jane@acme.com") -> str | None:
    """Render a streamlined search panel focused on business use cases."""
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    st.markdown("### Search & Analysis")
    st.caption("Search by customer ID, company name, customer name, or email.")
    with st.form(key="query_form", clear_on_submit=True):
        query = st.text_input(
            label="Search",
            value=default_value,
            placeholder=placeholder,
            label_visibility="collapsed",
        )
        col1, col2 = st.columns([2, 1])
        with col1:
            submitted = st.form_submit_button("Analyze", use_container_width=True, type="primary")
        with col2:
            clear_clicked = st.form_submit_button("Clear", use_container_width=True)

    if clear_clicked:
        st.session_state["adip_query_input"] = ""
        st.session_state["adip_selected_query"] = ""
        st.session_state["adip_auto_run"] = False
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    return query.strip() if submitted and query.strip() else None


def render_running_indicator() -> None:
    """Display a business-friendly progress message during analysis."""
    st.info("Reviewing customer context and preparing the next best actions for you.", icon="🤖")


def render_error(message: str) -> None:
    """Display an error banner in a console-like card."""
    st.markdown("<div class='dashboard-card status-danger'>", unsafe_allow_html=True)
    st.error(f"**Error:** {message}")
    st.markdown("</div>", unsafe_allow_html=True)


def render_agent_trace(execution_trace: list[dict]) -> None:
    """Executive-style workflow timeline."""
    if not execution_trace:
        return
    st.markdown("### Execution Timeline")
    with st.container():
        for step in execution_trace:
            agent = step.get("agent", "unknown")
            status = str(step.get("status", "")).lower()
            ts = _format_timestamp(step.get("timestamp"))
            icon = "✅" if status == "completed" else "⚠️" if status == "failed" else "⏳"
            st.markdown(f"<div class='dashboard-card' style='padding:0.75rem 0.95rem'>", unsafe_allow_html=True)
            st.markdown(f"<strong>{icon} {agent}</strong>")
            st.caption(f"Status: {status.title()} • {ts}")
            st.markdown("</div>", unsafe_allow_html=True)


def render_risk_flags(risk_flags: list[dict]) -> None:
    """Render risk flags as compact enterprise warnings."""
    if not risk_flags:
        return
    st.markdown("### Active Risks")
    for flag in risk_flags:
        level = str(flag.get("level", "LOW")).upper()
        desc = flag.get("description", "")
        mitigation = flag.get("mitigation", "")
        tone = "status-danger" if level in {"CRITICAL", "HIGH"} else "status-warn" if level == "MEDIUM" else "status-good"
        st.markdown(f"<div class='dashboard-card {tone}'>", unsafe_allow_html=True)
        st.markdown(f"**{level}**")
        st.write(desc)
        if mitigation:
            st.caption(f"Mitigation: {mitigation}")
        st.markdown("</div>", unsafe_allow_html=True)


def render_recommendations(recommendations: list[dict]) -> None:
    """Render recommendations as action cards with business context."""
    if not recommendations:
        st.info("No specific recommendations generated.")
        return

    st.markdown("### Recommended Actions")
    for i, rec in enumerate(recommendations, 1):
        action = rec.get("action", "")
        priority = str(rec.get("priority", "MEDIUM")).upper()
        conf = rec.get("confidence_score", 0)
        sensitivity = rec.get("time_sensitivity", "") or "Standard"
        rationale = rec.get("rationale", "")
        impact = rec.get("estimated_impact") or "Business impact to be confirmed"
        owner = rec.get("owner") or "Account team"
        due_date = rec.get("due_date") or "Next review cycle"
        tone = "status-danger" if priority == "HIGH" else "status-warn" if priority == "MEDIUM" else "status-good"
        st.markdown(f"<div class='dashboard-card {tone}'>", unsafe_allow_html=True)
        st.markdown(f"**{i}. {action}**")
        st.caption(f"Priority: {priority} • Confidence: {conf:.0%} • Due: {due_date}")
        st.write(rationale or impact)
        st.caption(f"Business impact: {impact} • Owner: {owner} • Urgency: {sensitivity}")
        st.markdown("</div>", unsafe_allow_html=True)


def render_metrics_row(summary: dict, result: Any | None = None) -> None:
    """Render a KPI grid for the current decision context."""
    meta = getattr(result, "metadata", {}) if result else {}
    entity_data = (meta.get("entity_data") or meta.get("customer_data") or {}) if isinstance(meta, dict) else {}
    cards = []
    cards.append(("Health Score", _normalize_value(entity_data.get("account_health") or entity_data.get("health_score") or "—"), "Current account health"))
    cards.append(("Churn Risk", _normalize_value(entity_data.get("churn_risk_score") or summary.get("overall_risk"), "—"), "Risk signal"))
    cards.append(("Renewal Countdown", _normalize_value(entity_data.get("contract_end_date") or entity_data.get("renewal_date") or entity_data.get("renewal_countdown"), "—"), "Contract timeline"))
    cards.append(("Open Tickets", _normalize_value(meta.get("open_tickets") or entity_data.get("open_tickets"), "—"), "Support activity"))
    cards.append(("Active Risks", _normalize_value(len(summary.get("risk_flags", [])), "0"), "Flags on record"))
    cards.append(("Sentiment", _normalize_value(entity_data.get("sentiment") or meta.get("sentiment"), "—"), "Customer tone"))
    cards.append(("Confidence", f"{summary.get('confidence', 0):.0%}", "Decision confidence"))
    cards.append(("Lifetime Value", _normalize_value(entity_data.get("lifetime_value") or entity_data.get("arr") or entity_data.get("annual_revenue"), "—"), "Revenue context"))

    cols = st.columns(4)
    for idx, (title, value, sub) in enumerate(cards):
        with cols[idx % 4]:
            st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-label'>{title}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-value'>{value}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-sub'>{sub}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


def render_history_sidebar(history: list[dict]) -> str | None:
    """Render a business-oriented sidebar with navigation and quick actions."""
    st.sidebar.markdown("## Business Workspace")
    st.sidebar.markdown("### Navigation")
    for item in ["Dashboard", "Customers", "Recent Analyses", "Saved Decisions", "High Priority Customers", "Quick Actions"]:
        st.sidebar.markdown(f"• {item}")
    st.sidebar.divider()

    st.sidebar.markdown("### Quick Actions")
    quick_actions = [
        ("🔍 Analyze CUST-002", "Analyze CUST-002"),
        ("📈 High Churn Customers", "Show me high churn customers"),
        ("📅 Upcoming Renewals", "Find customers with upcoming renewals"),
        ("⚠ Executive Escalations", "Show executive escalations"),
        ("💰 Upsell Opportunities", "Find upsell opportunities"),
        ("📋 SLA Violations", "Find customers with SLA violations"),
    ]
    for label, query in quick_actions:
        if st.sidebar.button(label, key=f"qa_{hash(label)}", use_container_width=True):
            return query

    st.sidebar.divider()
    st.sidebar.markdown("### Recent Analyses")
    if not history:
        st.sidebar.caption("No recent analyses yet.")
    else:
        for entry in history[:6]:
            q = entry.get("query", "") or "Untitled analysis"
            label = q[:35] + ("..." if len(q) > 35 else "")
            if st.sidebar.button(label, key=f"hist_{q}", use_container_width=True):
                return q
    return None


def render_customer_summary(result: Any | None) -> None:
    """Render an executive summary card for the current customer context."""
    if not result:
        return
    meta = getattr(result, "metadata", {}) if result else {}
    entity_data = (meta.get("entity_data") or meta.get("customer_data") or {}) if isinstance(meta, dict) else {}
    customer_id = getattr(result, "entity_id", None) or entity_data.get("customer_id") or meta.get("customer_id")
    if not customer_id and not entity_data:
        st.info("Run a customer-focused analysis to populate the executive summary.")
        return

    st.markdown("### Customer Summary")
    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns([1.1, 1.1, 1.0])
    with col_a:
        st.markdown(f"**Customer ID**\n{_normalize_value(customer_id, '—')}")
        st.markdown(f"**Company**\n{_normalize_value(entity_data.get('company_name') or entity_data.get('company'), '—')}")
        st.markdown(f"**Industry**\n{_normalize_value(entity_data.get('industry'), '—')}")
    with col_b:
        st.markdown(f"**Plan / Segment**\n{_normalize_value(entity_data.get('segment') or entity_data.get('plan'), '—')}")
        st.markdown(f"**ARR**\n{_normalize_value(entity_data.get('arr') or entity_data.get('annual_revenue') or entity_data.get('lifetime_value'), '—')}")
        st.markdown(f"**Health Score**\n{_normalize_value(entity_data.get('account_health') or entity_data.get('health_score'), '—')}")
    with col_c:
        st.markdown(f"**Churn Risk**\n{_normalize_value(entity_data.get('churn_risk_score') or '—', '—')}")
        st.markdown(f"**Renewal Date**\n{_normalize_value(entity_data.get('contract_end_date') or entity_data.get('renewal_date'), '—')}")
        st.markdown(f"**Customer Since**\n{_normalize_value(entity_data.get('customer_since'), '—')}")
    st.markdown("</div>", unsafe_allow_html=True)


def render_supporting_evidence(result: Any | None, knowledge_chunks: list[dict]) -> None:
    """Render evidence cards for knowledge, memory, CRM, and decisions."""
    if not result and not knowledge_chunks:
        return

    evidence_items: list[dict[str, Any]] = []
    for rec in getattr(result, "recommendations", []) or []:
        for ev in rec.evidence or []:
            evidence_items.append({
                "source": ev.source,
                "date": None,
                "summary": ev.description,
                "confidence": ev.weight,
            })

    for chunk in knowledge_chunks or []:
        evidence_items.append({
            "source": chunk.get("source", "Knowledge Document"),
            "date": chunk.get("date") or chunk.get("retrieved_at"),
            "summary": chunk.get("content", "")[:220],
            "confidence": chunk.get("similarity"),
        })

    if not evidence_items:
        st.info("No supporting evidence surfaced for this analysis yet.")
        return

    st.markdown("### Evidence & Context")
    for item in evidence_items[:6]:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.markdown(f"**{_normalize_value(item.get('source'), 'Source')}**")
        st.caption(f"Date: {_normalize_value(item.get('date'), 'Not recorded')}")
        st.write(item.get("summary") or "No summary available.")
        conf = item.get("confidence")
        if conf is not None:
            st.caption(f"Confidence: {conf:.0%}" if isinstance(conf, float) else f"Confidence: {_normalize_value(conf)}")
        st.markdown("</div>", unsafe_allow_html=True)


def render_validation_panel(summary: dict, result: Any | None = None) -> None:
    """Render validation cards for policy, compliance, SLA, and renewal checks."""
    requires_review = bool(summary.get("requires_human_review", False))
    risk_flags = summary.get("risk_flags", [])
    st.markdown("### Review Checks")
    checks = [
        ("Policy checks", "warning" if requires_review or risk_flags else "passed", "Policy review is required" if requires_review else "No policy blocker detected."),
        ("Compliance checks", "warning" if risk_flags else "passed", "Risk signals were surfaced for follow-up." if risk_flags else "Baseline compliance checks passed."),
        ("SLA validation", "warning" if risk_flags else "passed", "Service obligations should be monitored." if risk_flags else "No immediate SLA issues were surfaced."),
        ("Renewal validation", "warning" if risk_flags else "passed", "Renewal readiness should be reviewed." if risk_flags else "No blocking renewal issue detected."),
    ]
    for title, status, detail in checks:
        tone = "status-danger" if status == "failed" else "status-warn" if status == "warning" else "status-good"
        st.markdown(f"<div class='dashboard-card {tone}'>", unsafe_allow_html=True)
        st.markdown(f"**{title}**")
        st.caption(f"Status: {status.upper()}")
        st.write(detail)
        st.markdown("</div>", unsafe_allow_html=True)


def render_chat_toggle_button() -> bool:
    """Render a fixed bottom-right chat button for opening the assistant."""
    st.markdown(
        """
        <style>
            .adip-chat-toggle-wrapper {
                position: fixed;
                right: 1.5rem;
                bottom: 1.5rem;
                z-index: 9999;
                width: 72px;
                height: 72px;
            }
            .adip-chat-toggle-wrapper .stButton>button {
                width: 72px !important;
                height: 72px !important;
                border-radius: 50% !important;
                border: 1px solid rgba(255,255,255,0.18) !important;
                background: linear-gradient(135deg, rgba(56,189,248,0.96), rgba(129,140,248,0.96)) !important;
                color: #020617 !important;
                font-size: 1.25rem !important;
                font-weight: 700 !important;
                box-shadow: 0 18px 42px rgba(4,20,52,0.35) !important;
            }
            .adip-chat-toggle-wrapper .stButton>button:hover {
                transform: translateY(-1px);
                box-shadow: 0 20px 48px rgba(4,20,52,0.42) !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="adip-chat-toggle-wrapper">', unsafe_allow_html=True)
    clicked = st.button("💬", key="adip_chat_toggle", help="Open the business assistant chat")
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def render_chat_panel(chat_history: list[dict[str, Any]], chat_input: str | None = None) -> tuple[str, bool, bool]:
    """Render a floating assistant chat panel when the user toggles chat open."""
    st.markdown(
        """
        <style>
            .adip-chat-panel {
                position: fixed;
                right: 1.5rem;
                bottom: 6.5rem;
                width: min(420px, 92vw);
                max-height: 72vh;
                z-index: 9998;
                border-radius: 22px;
                background: rgba(8, 18, 35, 0.96);
                border: 1px solid rgba(148,163,184,0.18);
                box-shadow: 0 26px 60px rgba(0,0,0,0.35);
                padding: 0.95rem;
                backdrop-filter: blur(18px);
            }
            .adip-chat-panel .chat-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
            }
            .adip-chat-panel .chat-header .title {
                font-size: 1.05rem;
                font-weight: 700;
                margin-bottom: 0.05rem;
            }
            .adip-chat-panel .chat-header .subtitle {
                color: #94a3b8;
                font-size: 0.85rem;
            }
            .adip-chat-panel .chat-history {
                max-height: 38vh;
                overflow-y: auto;
                padding-right: 0.35rem;
                margin-top: 0.9rem;
                margin-bottom: 0.85rem;
            }
            .adip-chat-panel .chat-message {
                margin-bottom: 0.75rem;
                padding: 0.75rem 0.95rem;
                border-radius: 18px;
                line-height: 1.5;
                font-size: 0.92rem;
            }
            .adip-chat-panel .message-user {
                background: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.18);
            }
            .adip-chat-panel .message-assistant {
                background: rgba(59, 130, 246, 0.14);
                border: 1px solid rgba(96, 165, 250, 0.2);
            }
            .adip-chat-panel textarea {
                width: 100%;
                min-height: 110px;
                border-radius: 16px;
                border: 1px solid rgba(148,163,184,0.22);
                background: rgba(15,23,42,0.92);
                color: #e2e8f0;
                padding: 0.8rem;
            }
            .adip-chat-panel .chat-footer {
                display: flex;
                gap: 0.65rem;
                align-items: center;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="adip-chat-panel">', unsafe_allow_html=True)
    st.markdown(
        '<div class="chat-header"><div><div class="title">Business Assistant</div>'
        '<div class="subtitle">Ask about customers, risks, or next steps.</div></div></div>',
        unsafe_allow_html=True,
    )

    if not chat_history:
        st.markdown("<div class='dashboard-card' style='background: rgba(15,23,42,0.9);'>" , unsafe_allow_html=True)
        st.markdown("<strong>Welcome to the interactive assistant.</strong><br/>Use the chat to ask clarifying questions and get business-safe guidance.", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="chat-history">', unsafe_allow_html=True)
        for message in chat_history[-12:]:
            role = message.get("role", "assistant")
            text = message.get("message", "")
            style = "message-user" if role == "user" else "message-assistant"
            label = "You" if role == "user" else "Assistant"
            st.markdown(f"<div class='chat-message {style}'><strong>{label}</strong><br>{text}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.form(key="adip_chat_form", clear_on_submit=False):
        chat_text = st.text_area(
            "",
            value=chat_input or "",
            key="adip_chat_input",
            placeholder="Ask the assistant a business question...",
        )
        cols = st.columns([3, 1])
        with cols[0]:
            send_clicked = st.form_submit_button("Send")
        with cols[1]:
            close_clicked = st.form_submit_button("Close")

    st.markdown('</div>', unsafe_allow_html=True)
    return chat_text, send_clicked, close_clicked


def render_knowledge_chunks(chunks: list[dict]) -> None:
    """Legacy helper retained for compatibility with older call sites."""
    if not chunks:
        return
    st.markdown("### Knowledge Retrieved")
    for chunk in chunks:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.markdown(f"**{chunk.get('source', 'knowledge_base')}**")
        st.caption(chunk.get("content", "")[:240])
        st.markdown("</div>", unsafe_allow_html=True)
