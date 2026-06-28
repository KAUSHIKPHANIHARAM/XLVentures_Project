"""
config/resolver.py

Environment variable resolution for YAML configuration values.

Supports the ${VAR_NAME} and ${VAR_NAME:default_value} syntax throughout
all YAML config files. This keeps secrets out of version control.

Design:
    - Pure function-based (no state needed).
    - Operates recursively on nested dicts/lists.
    - Raises ConfigResolutionError on missing required env vars.
"""

from __future__ import annotations

import os
import re
from typing import Any


# Matches ${VAR_NAME} and ${VAR_NAME:default}
_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


class ConfigResolutionError(Exception):
    """Raised when a required environment variable is missing."""


def resolve_env_vars(value: Any) -> Any:
    """
    Recursively walk a config structure and replace all ${...} expressions
    with their environment variable values.

    Args:
        value: A string, dict, list, or scalar loaded from YAML.

    Returns:
        The same structure with all ${...} expressions resolved.

    Raises:
        ConfigResolutionError: If a required env var has no value and no default.
    """
    if isinstance(value, str):
        return _resolve_string(value)
    if isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    # int, float, bool, None — pass through unchanged
    return value


def _resolve_string(text: str) -> str:
    """Replace all ${VAR} / ${VAR:default} occurrences in a single string."""

    def _substitute(match: re.Match) -> str:
        var_name: str = match.group(1).strip()
        default: str | None = match.group(2)  # None if no colon+default provided

        env_value = os.environ.get(var_name)

        if env_value is not None:
            return env_value

        if default is not None:
            # An explicit default was provided (may be empty string — that's ok)
            return default

        raise ConfigResolutionError(
            f"Environment variable '{var_name}' is required but not set. "
            f"Add it to your .env file or export it before starting the platform."
        )

    return _ENV_PATTERN.sub(_substitute, text)
