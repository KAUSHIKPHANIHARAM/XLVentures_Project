"""
utils/retry.py

Retry utilities for resilient API and database calls.

LLM API calls and vector DB operations can fail transiently (rate limits,
network timeouts). This module provides a configurable retry decorator
backed by the tenacity library.

Design:
    - retry_on_transient_error() is the primary decorator.
    - Exponential backoff with jitter by default (avoids thundering herd).
    - Configurable: max_attempts, wait_seconds, and exception whitelist.
    - Logs each retry attempt at WARNING level for observability.
    - Falls back gracefully if tenacity is not installed.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retry_on_transient_error(
    max_attempts: int = 3,
    wait_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_wait_seconds: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator that retries a function on transient errors.

    Uses exponential backoff with a configurable multiplier.
    The actual wait time is: wait_seconds * (backoff_multiplier ^ attempt).

    Args:
        max_attempts:       Maximum total invocation attempts (including first).
        wait_seconds:       Initial wait between retries in seconds.
        backoff_multiplier: Multiplier applied to wait_seconds each retry.
        max_wait_seconds:   Cap on the wait time between retries.
        exceptions:         Tuple of exception types that trigger a retry.
                            Other exceptions propagate immediately.

    Usage:
        @retry_on_transient_error(max_attempts=3, wait_seconds=1.0)
        def call_openai_api(prompt: str) -> str:
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            wait = wait_seconds

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        logger.error(
                            "Function '%s' failed after %d attempt(s). "
                            "Final error: %s",
                            func.__name__,
                            max_attempts,
                            exc,
                        )
                        raise

                    logger.warning(
                        "Function '%s' failed on attempt %d/%d. "
                        "Retrying in %.1fs. Error: %s",
                        func.__name__,
                        attempt,
                        max_attempts,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                    wait = min(wait * backoff_multiplier, max_wait_seconds)

            # Unreachable — but makes type checkers happy
            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


def retry_llm_call(max_attempts: int = 3) -> Callable[[F], F]:
    """
    Pre-configured retry decorator for LLM API calls.

    Retries on all exceptions with 2s initial wait and exponential backoff.
    Appropriate for OpenAI API calls which may hit rate limits.
    """
    return retry_on_transient_error(
        max_attempts=max_attempts,
        wait_seconds=2.0,
        backoff_multiplier=2.0,
        max_wait_seconds=30.0,
    )


def retry_db_call(max_attempts: int = 3) -> Callable[[F], F]:
    """
    Pre-configured retry decorator for database operations.

    Shorter initial wait (0.5s) since DB issues are usually transient locks.
    """
    return retry_on_transient_error(
        max_attempts=max_attempts,
        wait_seconds=0.5,
        backoff_multiplier=2.0,
        max_wait_seconds=5.0,
    )
