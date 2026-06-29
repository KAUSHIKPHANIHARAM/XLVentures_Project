"""
frontend/app.py

Main Streamlit application for the Enterprise Decision Intelligence Platform.

Layout:
    Sidebar   — domain info, settings, query history
    Main area — query input, metrics, recommendations, risk flags, trace

Entry point (run via the system entry point only):
    streamlit run app/main.py

Do NOT run this file directly with streamlit — always use app/main.py
so that the .env file is loaded and sys.path is set up correctly first.
"""

from __future__ import annotations

import sys
import os
import threading
import time
from pathlib import Path

# Ensure project root is on the path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env when run directly (app/main.py handles this when used as entry point)
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

import streamlit as st
from utils.logging import get_logger

logger = get_logger(__name__)

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
        logger.info(
            "Platform bootstrap starting. LLM provider=%s, embedding provider=%s, active domain=%s",
            cfg.llm.provider,
            cfg.embedding.provider,
            cfg.active_domain,
        )
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
        logger.exception("Platform bootstrap failed.")
        return {"ok": False, "error": str(exc)}


_boot = _bootstrap()

if not _boot.get("ok", False):
    st.error("### ⚙️ Platform Setup Required")
    _err = _boot.get("error", "Unknown error")
    st.markdown(f"**Error:** `{_err}`")

    if "langchain-google-genai" in _err or "ChatGoogleGenerativeAI" in _err:
        st.warning(
            "This platform is configured to use Gemini/Google LLMs, but the required package "
            "`langchain-google-genai` is missing. Install it with: `pip install langchain-google-genai`."
        )

    if "API key for provider" in _err:
        st.warning(
            "Your LLM provider requires an API key. Check that your .env file contains the correct "
            "environment variable for the active provider (for example `GEMINI_API_KEY` when using Gemini)."
        )

    st.markdown("""
    ---
    ### Quick Setup

    **1. Create or update a `.env` file** in the project root:
    ```
    cp .env.example .env
    ```

    **2. Add your provider API key to `.env`:**
    ```
    OPENAI_API_KEY=sk-your-actual-key-here
    ```

    If you are using Gemini/Google, set:
    ```
    GEMINI_API_KEY=your-gemini-key
    LLM_PROVIDER=gemini
    EMBEDDING_PROVIDER=gemini
    ```

    **3. Restart the Streamlit server:**
    ```
    streamlit run app/main.py
    ```
    ---
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
    set_error, clear_error, is_chat_open, set_chat_open,
    get_chat_history, add_chat_message, get_chat_input, set_chat_input,
)
from frontend.components import (
    render_header, render_query_input, render_running_indicator,
    render_error, render_agent_trace, render_risk_flags,
    render_recommendations, render_metrics_row, render_history_sidebar,
    render_knowledge_chunks, render_customer_summary,
    render_supporting_evidence, render_validation_panel,
    render_chat_toggle_button, render_chat_panel,
)

init_session()
set_domain(domain.name)

# -----------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------
with st.sidebar:
    clicked_history = render_history_sidebar(get_history())
    if clicked_history:
        st.session_state["adip_selected_query"] = clicked_history

# -----------------------------------------------------------------------
# Main page
# -----------------------------------------------------------------------
render_header(
    "Enterprise Decision Intelligence Platform",
    subtitle="AI-powered Customer Success Decision Support",
)

# Manage query pre-filling and auto-running
if "adip_query_input" not in st.session_state:
    st.session_state["adip_query_input"] = ""

# If a query is clicked in the sidebar, set it in state and request auto-run
if "adip_selected_query" in st.session_state:
    st.session_state["adip_query_input"] = st.session_state.pop("adip_selected_query")
    st.session_state["adip_auto_run"] = True

auto_run = st.session_state.pop("adip_auto_run", False)
current_query = st.session_state.get("adip_query_input", "")

submitted_query = None

if auto_run and current_query:
    submitted_query = current_query
else:
    submitted_query = render_query_input(
        default_value=current_query,
        placeholder="e.g. CUST-002, Acme Corp, Jane Smith, jane@acme.com"
    )
    if submitted_query:
        st.session_state["adip_query_input"] = submitted_query

if get_error():
    render_error(get_error())
    clear_error()

# -----------------------------------------------------------------------
# Execute workflow on submit — runs in a background thread to keep
# Streamlit's WebSocket alive during long LLM calls
# -----------------------------------------------------------------------
if submitted_query:
    clear_error()
    set_running(True)
    clear_stream_log()
    render_running_indicator()

    # Shared mutable container for thread result
    _result_box: dict = {"done": False, "result": None, "error": None}

    def _run_workflow():
        try:
            r = executor.run(submitted_query, get_session_id())
            _result_box["result"] = r
        except Exception as exc:
            _result_box["error"] = str(exc)
        finally:
            _result_box["done"] = True

    _thread = threading.Thread(target=_run_workflow, daemon=True)
    _thread.start()

    # Keep Streamlit alive by updating the UI every 0.5 s while thread runs
    _steps = [
        "🔍 Routing query to specialist agents...",
        "📊 Fetching customer data...",
        "🧠 Analysing churn risk & sentiment...",
        "💡 Generating recommendations...",
        "✍️ Synthesising final response...",
    ]
    _placeholder = st.empty()
    _elapsed = 0
    _step_idx = 0
    while not _result_box["done"]:
        msg = _steps[_step_idx % len(_steps)]
        _placeholder.info(f"{msg}  *(elapsed: {_elapsed}s)*")
        time.sleep(0.5)
        _elapsed += 1
        if _elapsed % 4 == 0:          # advance step message every 4 s
            _step_idx += 1

    _placeholder.empty()
    _thread.join(timeout=5)

    if _result_box["error"]:
        set_error(_result_box["error"])
    elif _result_box["result"]:
        result = _result_box["result"]
        set_current_result(result)
        summary = formatter.to_summary_dict(result)
        add_to_history(submitted_query, summary)

    set_running(False)
    st.rerun()

# -----------------------------------------------------------------------
# Display current result
# -----------------------------------------------------------------------
current_result = get_current_result()
if current_result:
    summary = formatter.to_summary_dict(current_result)

    render_metrics_row(summary, current_result)
    st.divider()

    render_customer_summary(current_result)
    st.divider()

    col_left, col_right = st.columns([1.7, 1.0])

    with col_left:
        st.markdown("### Business Assessment")
        final_response = summary.get("final_response", "")
        if final_response:
            st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
            st.markdown(final_response)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No response generated.")

        st.divider()
        render_recommendations(summary.get("recommendations", []))

    with col_right:
        risk_flags = summary.get("risk_flags", [])
        if risk_flags:
            render_risk_flags(risk_flags)
            st.divider()
        render_validation_panel(summary, current_result)

    st.divider()

    knowledge_chunks = current_result.metadata.get("knowledge_chunks", [])
    render_supporting_evidence(current_result, knowledge_chunks)

else:
    st.markdown("<div class='dashboard-card' style='text-align:center; padding:2rem 1rem'>", unsafe_allow_html=True)
    st.markdown("## Ready to Analyze")
    st.write("Launch an enterprise-style customer and decision review from the search panel above.")
    st.caption(f"Powered by LangGraph · ChromaDB · {cfg.llm.provider.title()}")
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# Chat assistant widget
# -----------------------------------------------------------------------
if render_chat_toggle_button():
    set_chat_open(not is_chat_open())

if is_chat_open():
    chat_text, send_clicked, close_clicked = render_chat_panel(
        get_chat_history(), get_chat_input()
    )
    if close_clicked:
        set_chat_open(False)
    if send_clicked and chat_text and chat_text.strip():
        user_message = chat_text.strip()
        set_chat_input("")
        add_chat_message("user", user_message)
        if current_result:
            assistant_message = (
                "I reviewed the latest customer analysis. "
                f"Key insight: {summary.get('final_response', 'No summary available.')} "
                f"Top action: {summary.get('recommendations', [{}])[0].get('action', 'Review the recommendation list.')}"
            )
        else:
            assistant_message = (
                "Send a query through the search field to analyze customers, risk, or policy scenarios. "
                "I can help you interpret the results once the analysis completes."
            )
        add_chat_message("assistant", assistant_message)
