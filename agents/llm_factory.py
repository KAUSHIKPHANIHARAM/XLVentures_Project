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

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore[assignment,misc]

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]

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
        ImportError: If the required provider package is missing.
    """
    provider = llm_config.provider.lower()
    cache_key = f"{provider}:{llm_config.model}:{llm_config.temperature}:{llm_config.max_tokens}"

    logger.debug(
        "Resolving LLM provider=%s model=%s api_key_env=%s",
        provider,
        llm_config.model,
        llm_config.api_key_env,
    )

    if cache_key in _llm_cache:
        return _llm_cache[cache_key]
    
    # Resolve the API key based on provider
    api_key = os.environ.get(llm_config.api_key_env, "")
    if not api_key:
        if provider in ("google", "gemini"):
            api_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        logger.error(
            "Missing API key for provider '%s'. Checked env vars: %s",
            provider,
            llm_config.api_key_env,
        )
        raise ValueError(
            f"API key for provider '{provider}' not found. "
            f"Set the '{llm_config.api_key_env}' environment variable "
            f"or add it to your .env file."
        )

    # Google Gemini support
    if provider in ("google", "gemini"):
        if ChatGoogleGenerativeAI is None:
            logger.error(
                "Provider '%s' requires 'langchain-google-genai', but it is not installed.",
                provider,
            )
            raise ImportError(
                "The Gemini/Google LLM provider requires the package 'langchain-google-genai'. "
                "Install it with: pip install langchain-google-genai"
            )

        # Map GPT models to Gemini for compatibility with domain configs
        model_name = llm_config.model
        if "gpt" in model_name.lower():
            model_name = "gemini-2.5-flash"

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens or 4096,
            google_api_key=api_key,
            max_retries=llm_config.max_retries,
        )
        _llm_cache[cache_key] = llm
        logger.info(
            "ChatGoogleGenerativeAI created. Model='%s', Temperature=%.1f.",
            model_name,
            llm_config.temperature,
        )
        return llm

    # OpenAI fallback
    if ChatOpenAI is None:
        logger.error("Provider '%s' requires 'langchain-openai', but it is not installed.", provider)
        raise ImportError(
            "The OpenAI provider requires the package 'langchain-openai'. "
            "Install it with: pip install langchain-openai"
        )

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


def reset_llm_cache() -> None:
    """Clear the LLM cache (for tests only)."""
    global _llm_cache  # noqa: PLW0603
    _llm_cache = {}
