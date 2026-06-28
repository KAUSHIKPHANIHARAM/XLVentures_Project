"""
utils/logging.py

Platform-wide logging factory and setup.

Provides a consistent logging configuration driven by LoggingConfig
from the platform YAML. Every module in the platform calls
get_logger(__name__) to get a properly configured logger.

Design:
    - setup_logging() is idempotent — safe to call multiple times.
    - All loggers share the root 'adip' namespace (Agentic Decision
      Intelligence Platform) for easy filtering.
    - Optional file handler for persistent log files.
    - Console handler always added for development visibility.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.schemas import LoggingConfig

# Root namespace for all platform loggers
PLATFORM_LOGGER_NAME = "adip"

_is_configured = False


def setup_logging(log_config: "LoggingConfig") -> None:
    """
    Configure the platform-wide logging system from LoggingConfig.

    Should be called once at application startup (in app/main.py).
    Subsequent calls are no-ops (idempotent).

    Args:
        log_config: Validated LoggingConfig from platform settings.
    """
    global _is_configured  # noqa: PLW0603
    if _is_configured:
        return

    root_logger = logging.getLogger(PLATFORM_LOGGER_NAME)
    root_logger.setLevel(log_config.level)

    formatter = logging.Formatter(fmt=log_config.format)

    # --- Console handler (always present) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_config.level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # --- File handler (optional) ---
    if log_config.file_path:
        file_path = Path(log_config.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_config.level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers in non-debug mode
    if log_config.level != "DEBUG":
        for noisy_logger in ("httpx", "httpcore", "openai", "chromadb", "urllib3"):
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    _is_configured = True
    root_logger.info(
        "Logging configured. Level=%s, File=%s",
        log_config.level,
        log_config.file_path or "none",
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a namespaced logger for a platform module.

    Automatically prefixes the name with the platform namespace.

    Args:
        name: Typically __name__ of the calling module.
              E.g. 'agents.router' → logger named 'adip.agents.router'

    Returns:
        A configured logging.Logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Agent started.")
    """
    # Strip the top-level package prefix if it's already there
    if name.startswith(PLATFORM_LOGGER_NAME + "."):
        full_name = name
    else:
        full_name = f"{PLATFORM_LOGGER_NAME}.{name}"

    return logging.getLogger(full_name)


def reset_logging() -> None:
    """Reset logging configuration (for tests only)."""
    global _is_configured  # noqa: PLW0603
    root_logger = logging.getLogger(PLATFORM_LOGGER_NAME)
    root_logger.handlers.clear()
    _is_configured = False
