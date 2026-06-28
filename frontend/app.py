"""
frontend/app.py

Main Streamlit application for the Enterprise Decision Intelligence Platform.

Layout:
    Sidebar   — domain info, settings, query history
    Main area — query input, metrics, recommendations, risk flags, trace

Entry point:
    streamlit run app/main.py  (which imports this module)
    or directly: streamlit run frontend/app.py
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure project root is on the path when run directly
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

# -----------------------------------------------------------------------
# Page configuration (must be first Streamlit call)
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="Decision Intelligence Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Enterprise Reusable Agentic Decision Intelligence Platform",
    },
)

# -----------------------------------------------------------------------
# Bootstrap platform (cached — runs once per server process)
# -----------------------------------------------------------------------
@st.cache_resource(show_spinner="🚀 Bootstrapping platform...")
def _bootstrap():
    """Initialize all platform layers. Cached for the lifetime of the server."""
    try:
        os.environ.setdefault("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

        from config.settings import initialize
        from utils import setup_logging
        from data import bootstrap_data_layer
        from memory import get_memory_store
        from knowledge import bootstrap_knowledge_layer
        from connectors import get_connector
        from agents.tool_implementations import register_all_tools
        from registry import register_domain_tools, register_domain_agents
        from workflow.executor import WorkflowExecutor
        from decision.formatter import DecisionFormatter

        cfg = initialize("config/platform.yaml", "config/domains", None)
        setup_logging(cfg.logging)
        domain = cfg.current_domain

        bootstrap_data_layer(cfg, seed=True, force_reseed=False)
        store = get_memory_store(cfg.vector_db, cfg.embedding)
        retrieval_svc = bootstrap_knowledge_layer(cfg, store, force_reingest=False)
        connector = get_connector(domain.name)
        register_all_tools(connector, retrieval_svc)
        tools = register_domain_tools(domain)
        register_domain_agents(domain, cfg.llm, tools)

        executor = WorkflowExecutor(domain, cfg, retrieval_svc)
        formatter = DecisionFormatter()

        return {"ok": True, "cfg": cfg, "domain": domain,
                "executor": executor, "formatter": formatter}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


_boot = _bootstrap()

if not _boot.get("ok", False):
    st.error("### ⚙️ Platform Setup Required")
    _err = _boot.get("error", "Unknown error")
    st.markdown(f"**Error:** `{_err}`")
    st.markdown("""
    ---
    ### Quick Setup

    **1. Create a `.env` file** in the project root:
    ```
    cp .env.example .env
    ```

    **2. Add your OpenAI API key to `.env`:**
    ```
    OPENAI_API_KEY=sk-your-actual-key-here
    ```

    **3. Restart the Streamlit server:**
    ```
    streamlit run app/main.py
    ```
    ---
    The platform requires an OpenAI API key to power its multi-agent LLM workflows.
    """)
    st.stop()

cfg = _boot["cfg"]
domain = _boot["domain"]
executor = _boot["executor"]
formatter = _boot["formatter"]

# -----------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------
from frontend.ui_state import (
    init_session, get_history, add_to_history, get_current_result,
    set_current_result, get_session_id, set_domain, is_running,
    set_running, get_stream_log, clear_stream_log, get_error,
    set_error, clear_error,
)
from frontend.components import (
    render_header, render_query_input, render_running_indicator,
    render_error, render_agent_trace, render_risk_flags,
    render_recommendations, render_metrics_row, render_history_sidebar,
    render_knowledge_chunks,
)

init_session()
set_domain(domain.name)

# -----------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Platform")
    st.markdown(f"**Platform:** {cfg.platform_name}")
    st.markdown(f"**Version:** {cfg.version}")
    st.markdown(f"**Domain:** {domain.display_name if hasattr(domain, 'display_name') else domain.name}")
    st.markdown(f"**Session:** `{get_session_id()[:8]}...`")
    st.divider()

    # Example queries
    st.markdown("### 💡 Try These")
    _EXAMPLE_QUERIES = [
        "What is the churn risk for customer 2 and what should we do?",
        "Show me all premium customers with high churn risk",
        "What is the policy for handling billing disputes?",
        "Analyze the sentiment of customer 3's recent interactions",
        "Find customers who have had SLA violations",
    ]
    for q in _EXAMPLE_QUERIES:
        if st.button(q[:55] + "...", key=f"ex_{hash(q)}", use_container_width=True):
            st.session_state["adip_selected_query"] = q

    st.divider()
    st.markdown("### 📜 History")
    clicked_history = render_history_sidebar(get_history())
    if clicked_history:
        st.session_state["adip_selected_query"] = clicked_history

# -----------------------------------------------------------------------
# Main page
# -----------------------------------------------------------------------
render_header(cfg.platform_name, domain.name.replace("_", " ").title())

# Show error if any
if get_error():
    render_error(get_error())
    clear_error()

# Pre-fill query if selected from sidebar
prefill = st.session_state.pop("adip_selected_query", "") if "adip_selected_query" in st.session_state else ""

# Query input
if prefill:
    st.text_area("Pre-filled query", value=prefill, key="_prefill_display", height=60,
                 label_visibility="collapsed", disabled=True)

submitted_query = render_query_input(
    placeholder=(
        prefill or "Ask a question about your customers, risks, or policies..."
    )
)

# -----------------------------------------------------------------------
# Execute workflow on submit
# -----------------------------------------------------------------------
if submitted_query:
    clear_error()
    set_running(True)
    clear_stream_log()

    with st.spinner("🤖 Multi-agent workflow running..."):
        try:
            result = executor.run(submitted_query, get_session_id())
            set_current_result(result)
            summary = formatter.to_summary_dict(result)
            add_to_history(submitted_query, summary)
        except Exception as exc:
            set_error(str(exc))
            result = None
            summary = None
        finally:
            set_running(False)

    if result and summary:
        st.rerun()

# -----------------------------------------------------------------------
# Display current result
# -----------------------------------------------------------------------
current_result = get_current_result()
if current_result:
    summary = formatter.to_summary_dict(current_result)

    # 4-metric bar
    render_metrics_row(summary)
    st.divider()

    # Main content in two columns
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### 📋 Answer")
        final_response = summary.get("final_response", "")
        if final_response:
            st.markdown(final_response)
        else:
            st.info("No response generated.")

        st.divider()
        render_recommendations(summary.get("recommendations", []))

    with col_right:
        # Risk flags
        risk_flags = summary.get("risk_flags", [])
        if risk_flags:
            render_risk_flags(risk_flags)
            st.divider()

        # Knowledge chunks used
        knowledge_chunks = current_result.metadata.get("knowledge_chunks", [])
        render_knowledge_chunks(knowledge_chunks)

        # Reasoning chain
        if current_result.reasoning_chain:
            with st.expander("🧠 Reasoning Chain", expanded=False):
                for step in current_result.reasoning_chain:
                    st.markdown(f"- {step}")

    st.divider()

    # Execution trace (bottom, full width)
    exec_trace = current_result.metadata.get("execution_trace", [])
    render_agent_trace(exec_trace)

    # Download
    with st.expander("⬇️ Export Result (JSON)", expanded=False):
        st.json(summary)
        json_str = formatter.to_json(current_result)
        st.download_button(
            label="Download Full JSON",
            data=json_str,
            file_name="decision_result.json",
            mime="application/json",
        )

else:
    # Welcome state — no result yet
    st.markdown("""
    <div style="text-align:center; padding:60px 0; opacity:0.6">
        <h2>🧠 Ready to Analyze</h2>
        <p>Ask a question in the input above or pick an example from the sidebar.</p>
        <p style="font-size:0.85em">Powered by LangGraph · ChromaDB · OpenAI</p>
    </div>
    """, unsafe_allow_html=True)
