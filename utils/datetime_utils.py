"""
utils/datetime_utils.py

Datetime helpers for consistent timestamp handling across the platform.

Design:
    - Always work in UTC internally; format for display only at the boundary.
    - Use ISO-8601 strings as the canonical format for storage (SQLite
      does not have a native datetime type).
    - Never import datetime directly in other modules — use these helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return utc_now().isoformat()


def parse_iso(timestamp: str) -> datetime:
    """
    Parse an ISO-8601 timestamp string into a timezone-aware datetime.

    Args:
        timestamp: ISO-8601 string, e.g. '2024-01-15T10:30:00+00:00'.

    Returns:
        A timezone-aware datetime object.

    Raises:
        ValueError: If the string cannot be parsed as ISO-8601.
    """
    dt = datetime.fromisoformat(timestamp)
    if dt.tzinfo is None:
        # Assume UTC if no timezone info is present
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_for_display(timestamp: str, fmt: str = "%d %b %Y, %H:%M UTC") -> str:
    """
    Format an ISO-8601 timestamp for human-readable display.

    Args:
        timestamp: ISO-8601 string.
        fmt:       strftime format string.

    Returns:
        Formatted date/time string.
    """
    try:
        dt = parse_iso(timestamp)
        return dt.strftime(fmt)
    except (ValueError, TypeError):
        return timestamp  # Return as-is if parsing fails


def days_since(timestamp: str) -> int:
    """
    Return the number of whole days elapsed since a given ISO-8601 timestamp.

    Args:
        timestamp: ISO-8601 string representing a past datetime.

    Returns:
        Integer number of days elapsed (0 = today).
    """
    try:
        past = parse_iso(timestamp)
        delta = utc_now() - past
        return max(0, delta.days)
    except (ValueError, TypeError):
        return 0


def is_recent(timestamp: str, within_days: int = 7) -> bool:
    """
    Check whether a timestamp falls within the last `within_days` days.

    Args:
        timestamp:   ISO-8601 string to check.
        within_days: Threshold in days.

    Returns:
        True if the timestamp is within the threshold.
    """
    return days_since(timestamp) <= within_days
