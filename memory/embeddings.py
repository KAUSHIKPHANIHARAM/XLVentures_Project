"""
memory/embeddings.py

Embedding function factory for the platform.

Provides a ChromaDB-compatible embedding function based on the
EmbeddingConfig from platform.yaml.

Strategy:
    1. If OPENAI_API_KEY is set and provider is 'openai' → use
       ChromaDB's built-in OpenAIEmbeddingFunction (no extra deps).
    2. Fallback → ChromaDB's DefaultEmbeddingFunction (sentence-transformers,
       runs locally with no API key — used for smoke testing).

Design:
    - Returns a callable that ChromaDB accepts as its embedding_function.
    - Singleton per (provider, model) pair to avoid re-initialising.
    - All configuration comes from EmbeddingConfig — not hardcoded.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from config.schemas import EmbeddingConfig

logger = logging.getLogger(__name__)

_embedding_fn_cache: dict[str, Any] = {}


def get_embedding_function(embedding_config: "EmbeddingConfig") -> Any:
    """
    Return a ChromaDB-compatible embedding function.

    Args:
        embedding_config: EmbeddingConfig from platform settings.

    Returns:
        A callable embedding function accepted by chromadb.Collection.
    """
    cache_key = f"{embedding_config.provider}:{embedding_config.model}"

    if cache_key in _embedding_fn_cache:
        return _embedding_fn_cache[cache_key]

    fn = _create_embedding_function(embedding_config)
    _embedding_fn_cache[cache_key] = fn
    return fn


def _create_embedding_function(embedding_config: "EmbeddingConfig") -> Any:
    """Instantiate the embedding function based on provider config."""
    provider = embedding_config.provider.lower()
    api_key = os.environ.get(embedding_config.api_key_env, "")

    if provider == "openai" and api_key and not api_key.startswith("sk-test"):
        return _build_openai_embedding_fn(api_key, embedding_config.model)

    # Fallback: local embeddings (no API key needed — great for smoke tests)
    logger.info(
        "OpenAI API key not detected or is a test key. "
        "Using ChromaDB local embedding function (sentence-transformers). "
        "Set OPENAI_API_KEY in .env for production-quality embeddings."
    )
    return _build_default_embedding_fn()


def _build_openai_embedding_fn(api_key: str, model: str) -> Any:
    """Build ChromaDB's built-in OpenAI embedding function."""
    try:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction  # type: ignore[import-untyped]

        logger.info("Using OpenAI embedding function. Model='%s'.", model)
        return OpenAIEmbeddingFunction(api_key=api_key, model_name=model)
    except ImportError:
        logger.warning(
            "chromadb.utils.embedding_functions not available. "
            "Falling back to local embeddings."
        )
        return _build_default_embedding_fn()


def _build_default_embedding_fn() -> Any:
    """Build ChromaDB's default local embedding function."""
    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction  # type: ignore[import-untyped]

        logger.info("Using ChromaDB DefaultEmbeddingFunction (local sentence-transformers).")
        return DefaultEmbeddingFunction()
    except (ImportError, Exception) as exc:
        logger.warning("DefaultEmbeddingFunction unavailable: %s. Using None.", exc)
        return None
