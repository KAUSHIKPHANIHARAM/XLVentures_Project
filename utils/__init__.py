"""
utils/__init__.py

Public API for the utils module.

Usage:
    from utils import get_logger, setup_logging
    from utils import chunk_text, truncate_text, sanitize_string
    from utils import utc_now_iso, days_since
    from utils import retry_llm_call, retry_db_call
    from utils import parse_llm_json, safe_json_loads
"""

# Logging
from utils.logging import get_logger, reset_logging, setup_logging

# Text
from utils.text import (
    chunk_text,
    dedent_and_strip,
    extract_json_block,
    format_as_bullet_list,
    sanitize_string,
    truncate_text,
)

# Datetime
from utils.datetime_utils import (
    days_since,
    format_for_display,
    is_recent,
    parse_iso,
    utc_now,
    utc_now_iso,
)

# Retry
from utils.retry import retry_db_call, retry_llm_call, retry_on_transient_error

# JSON
from utils.json_utils import (
    extract_field,
    parse_llm_json,
    safe_json_dumps,
    safe_json_loads,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "reset_logging",
    # Text
    "chunk_text",
    "truncate_text",
    "sanitize_string",
    "dedent_and_strip",
    "format_as_bullet_list",
    "extract_json_block",
    # Datetime
    "utc_now",
    "utc_now_iso",
    "parse_iso",
    "format_for_display",
    "days_since",
    "is_recent",
    # Retry
    "retry_on_transient_error",
    "retry_llm_call",
    "retry_db_call",
    # JSON
    "parse_llm_json",
    "safe_json_loads",
    "safe_json_dumps",
    "extract_field",
]
