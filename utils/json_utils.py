"""
utils/json_utils.py

Safe JSON parsing helpers for handling LLM outputs and config values.

LLM outputs are often almost-valid JSON: they may have trailing commas,
markdown fences, or prose before/after the JSON block. These helpers
handle those cases gracefully without crashing the workflow.

Design:
    - All functions return None / empty on failure rather than raising.
    - parse_llm_json() is the primary entry point for LLM output parsing.
    - Uses utils.text.extract_json_block to strip markdown fences first.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from utils.text import extract_json_block

logger = logging.getLogger(__name__)


def parse_llm_json(text: str) -> dict[str, Any] | None:
    """
    Parse a JSON dict from LLM output text.

    Handles:
        - Raw JSON: '{"key": "value"}'
        - Fenced JSON: '```json\n{"key": "value"}\n```'
        - JSON embedded in prose: 'Here is the result:\n{"key": "value"}'

    Args:
        text: Raw text from an LLM response.

    Returns:
        Parsed dict, or None if parsing fails.
    """
    if not text or not text.strip():
        return None

    # Try extracting a JSON block first (handles fenced code)
    json_str = extract_json_block(text) or text.strip()

    try:
        result = json.loads(json_str)
        if isinstance(result, dict):
            return result
        logger.warning("LLM JSON parsed but is not a dict: %s", type(result).__name__)
        return None
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM JSON output: %s | Text: %.100s", exc, text)
        return None


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Parse a JSON string, returning a default value on failure.

    Args:
        text:    JSON string to parse.
        default: Value to return if parsing fails.

    Returns:
        Parsed Python object, or `default` on failure.
    """
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, indent: int | None = None) -> str:
    """
    Serialize an object to a JSON string, returning '{}' on failure.

    Args:
        obj:    Object to serialize.
        indent: Optional indentation for pretty-printing.

    Returns:
        JSON string, or '{}' if serialisation fails.
    """
    try:
        return json.dumps(obj, indent=indent, default=str, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        logger.warning("Failed to serialize object to JSON: %s", exc)
        return "{}"


def extract_field(
    data: dict[str, Any],
    key: str,
    default: Any = None,
    cast: type | None = None,
) -> Any:
    """
    Safely extract a field from a dict with optional type casting.

    Args:
        data:    Source dictionary.
        key:     Key to extract.
        default: Default if key is missing or value is None.
        cast:    Optional type to cast the value to (e.g. float, int, str).

    Returns:
        The field value, cast if requested, or default.
    """
    value = data.get(key)
    if value is None:
        return default
    if cast is not None:
        try:
            return cast(value)
        except (ValueError, TypeError):
            return default
    return value
