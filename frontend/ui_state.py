"""
frontend/ui_state.py

UIState — manages Streamlit session state for the platform UI.

Centralises all st.session_state keys in one typed dataclass-like wrapper.
The UI never accesses st.session_state directly — it goes through UIState.

This prevents key collision bugs across pages and makes the state contract
explicit and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st

# Session state keys — all prefixed with 'adip_' to prevent collision
_PREFIX = "adip_"

_DEFAULTS: dict[str, Any] = {
    "history":          [],          # list of {query, result_dict, timestamp}
    "current_result":   None,        # DecisionResult (last run)
    "session_id":       "",          # UUID for this browser session
    "domain":           "",          # current domain name
    "is_running":       False,       # True while workflow is executing
    "stream_log":       [],          # list of agent step strings for live log
    "error_message":    "",          # last error to display
    "selected_query":   "",          # query chosen from history
}


def _key(name: str) -> str:
    return _PREFIX + name


def init_session() -> None:
    """Initialize all session state keys with their defaults (idempotent)."""
    import uuid
    for name, default in _DEFAULTS.items():
        k = _key(name)
        if k not in st.session_state:
            st.session_state[k] = default

    # Session ID is generated once per browser session
    if not st.session_state[_key("session_id")]:
        st.session_state[_key("session_id")] = str(uuid.uuid4())


# -----------------------------------------------------------------------
# Typed accessors
# -----------------------------------------------------------------------

def get_history() -> list[dict]:
    return st.session_state.get(_key("history"), [])

def add_to_history(query: str, result_dict: dict) -> None:
    from utils.datetime_utils import utc_now_iso
    history = get_history()
    history.insert(0, {
        "query": query,
        "result": result_dict,
        "timestamp": utc_now_iso()[:19].replace("T", " "),
    })
    st.session_state[_key("history")] = history[:20]  # keep last 20

def get_current_result() -> Any | None:
    return st.session_state.get(_key("current_result"))

def set_current_result(result: Any) -> None:
    st.session_state[_key("current_result")] = result

def get_session_id() -> str:
    return st.session_state.get(_key("session_id"), "")

def get_domain() -> str:
    return st.session_state.get(_key("domain"), "")

def set_domain(domain: str) -> None:
    st.session_state[_key("domain")] = domain

def is_running() -> bool:
    return st.session_state.get(_key("is_running"), False)

def set_running(value: bool) -> None:
    st.session_state[_key("is_running")] = value

def get_stream_log() -> list[str]:
    return st.session_state.get(_key("stream_log"), [])

def append_stream_log(message: str) -> None:
    log = get_stream_log()
    log.append(message)
    st.session_state[_key("stream_log")] = log

def clear_stream_log() -> None:
    st.session_state[_key("stream_log")] = []

def get_error() -> str:
    return st.session_state.get(_key("error_message"), "")

def set_error(message: str) -> None:
    st.session_state[_key("error_message")] = message

def clear_error() -> None:
    st.session_state[_key("error_message")] = ""
