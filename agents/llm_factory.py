"""
agents/llm_factory.py

LLM factory — creates and caches ChatOpenAI instances from LLMConfig.

Design:
    - One ChatOpenAI instance per unique config signature (model + temp + tokens).
    - Raises a clear error if the OpenAI API key is missing.
    - Supports per-agent model overrides while sharing instances where possible.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from config.schemas import LLMConfig

logger = logging.getLogger(__name__)

_llm_cache: dict[str, Any] = {}


def get_llm(llm_config: "LLMConfig") -> Any:
    """
    Return a cached ChatOpenAI instance for the given config.

    Args:
        llm_config: LLMConfig from platform settings or agent override.

    Returns:
        A ChatOpenAI instance.

    Raises:
        ValueError: If the API key environment variable is not set.
    """
    cache_key = f"{llm_config.model}:{llm_config.temperature}:{llm_config.max_tokens}"

    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    api_key = os.environ.get(llm_config.api_key_env, "")
    if not api_key:
        raise ValueError(
            f"OpenAI API key not found. "
            f"Set the '{llm_config.api_key_env}' environment variable "
            f"or add it to your .env file."
        )

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=llm_config.model,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            api_key=api_key,
            timeout=llm_config.timeout_seconds,
            max_retries=llm_config.max_retries,
        )
        _llm_cache[cache_key] = llm
        logger.info(
            "ChatOpenAI created. Model='%s', Temperature=%.1f.",
            llm_config.model,
            llm_config.temperature,
        )
        return llm

    except ImportError as exc:
        raise ImportError(
            "langchain-openai is not installed. Run: pip install langchain-openai"
        ) from exc


def reset_llm_cache() -> None:
    """Clear the LLM cache (for tests only)."""
    global _llm_cache  # noqa: PLW0603
    _llm_cache = {}
