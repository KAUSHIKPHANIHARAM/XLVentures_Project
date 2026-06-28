"""
config/settings.py

Singleton settings manager for the platform.

Provides the single, globally-accessible PlatformConfig instance.
All modules import from here — never from the loader or validator directly.

Design:
    - Thread-safe lazy initialization via a module-level lock.
    - Supports both file-based init and programmatic init (for tests).
    - Loads .env file automatically if python-dotenv is installed.
    - Exposes a simple get_config() function — the only public API.

Usage:
    from config.settings import get_config

    cfg = get_config()
    print(cfg.llm.model)
    print(cfg.current_domain.name)
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from config.loader import ConfigLoader
from config.schemas import PlatformConfig
from config.validator import validate_platform_config

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_config: PlatformConfig | None = None

# Default paths — relative to the project root
DEFAULT_PLATFORM_CONFIG = Path("config/platform.yaml")
DEFAULT_DOMAINS_DIR = Path("config/domains")


def initialize(
    platform_yaml: str | Path = DEFAULT_PLATFORM_CONFIG,
    domains_dir: str | Path = DEFAULT_DOMAINS_DIR,
    extra_env_file: str | Path | None = Path(".env"),
    force_reload: bool = False,
) -> PlatformConfig:
    """
    Initialize the platform configuration from YAML files.

    Must be called once at application startup before get_config() is used.
    Subsequent calls return the cached instance unless force_reload=True.

    Args:
        platform_yaml:  Path to the base platform YAML config.
        domains_dir:    Directory containing domain YAML files (*.yaml).
        extra_env_file: Path to a .env file to load before resolving env vars.
                        Ignored if the file does not exist or dotenv is unavailable.
        force_reload:   If True, discards the cached config and re-reads from disk.

    Returns:
        The validated, frozen PlatformConfig.
    """
    global _config  # noqa: PLW0603

    with _lock:
        if _config is not None and not force_reload:
            return _config

        _load_dotenv(extra_env_file)
        raw = _build_raw_config(platform_yaml, domains_dir)
        _config = validate_platform_config(raw)
        logger.info(
            "Platform '%s' v%s initialized. Active domain: '%s'.",
            _config.platform_name,
            _config.version,
            _config.active_domain,
        )
        return _config


def get_config() -> PlatformConfig:
    """
    Return the initialized PlatformConfig.

    Raises:
        RuntimeError: If initialize() has not been called yet.
    """
    if _config is None:
        raise RuntimeError(
            "Platform config has not been initialized. "
            "Call config.settings.initialize() at application startup."
        )
    return _config


def reset() -> None:
    """
    Clear the cached config (intended for use in tests only).
    """
    global _config  # noqa: PLW0603
    with _lock:
        _config = None
    logger.debug("Platform config reset (test mode).")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _load_dotenv(env_file: str | Path | None) -> None:
    """Attempt to load a .env file using python-dotenv if available."""
    if env_file is None:
        return
    env_path = Path(env_file)
    if not env_path.exists():
        logger.debug(".env file not found at '%s' — skipping.", env_path)
        return
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]

        loaded = load_dotenv(dotenv_path=env_path, override=False)
        if loaded:
            logger.debug("Loaded environment variables from '%s'.", env_path)
    except ImportError:
        logger.debug(
            "python-dotenv not installed. Skipping .env file load. "
            "Install it with: pip install python-dotenv"
        )


def _build_raw_config(
    platform_yaml: str | Path,
    domains_dir: str | Path,
) -> dict[str, Any]:
    """
    Load the base platform YAML and merge all discovered domain YAMLs.

    Domain YAML files in `domains_dir` are loaded independently and
    inserted into the 'domains' key of the merged config dict.
    """
    # 1. Load base platform config (no domain data yet)
    raw = ConfigLoader.load(base_path=platform_yaml, resolve_env=True)

    # 2. Discover and load all domain files
    domains_path = Path(domains_dir)
    domain_files = sorted(domains_path.glob("*.yaml")) if domains_path.exists() else []

    if not domain_files:
        logger.warning(
            "No domain YAML files found in '%s'. "
            "The platform will start with no active domains.",
            domains_path,
        )

    raw.setdefault("domains", {})
    for domain_file in domain_files:
        domain_data = ConfigLoader.load_domain(domain_file, resolve_env=True)
        domain_name = domain_data.get("name")
        if not domain_name:
            logger.warning(
                "Domain file '%s' has no 'name' field — skipping.", domain_file
            )
            continue
        raw["domains"][domain_name] = domain_data
        logger.debug("Discovered domain config: '%s' from '%s'.", domain_name, domain_file)

    return raw
