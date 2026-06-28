"""
config/loader.py

YAML configuration file loading with environment variable resolution
and multi-file deep-merge support.

Responsibilities:
    1. Read one or more YAML files from disk.
    2. Deep-merge them in order (later files override earlier ones).
    3. Apply environment variable resolution via the resolver module.
    4. Return a plain Python dict ready for Pydantic validation.

Design:
    - ConfigLoader is a stateless service (all methods are class-level).
    - Supports loading a base config + domain overlay in a single call.
    - Never validates — that is the validator's responsibility.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml

from config.resolver import resolve_env_vars

logger = logging.getLogger(__name__)


class ConfigLoadError(Exception):
    """Raised when a YAML config file cannot be read or parsed."""


class ConfigLoader:
    """
    Loads and merges YAML configuration files.

    Usage:
        raw = ConfigLoader.load(
            base_path="config/platform.yaml",
            overrides=["config/domains/customer_management.yaml"],
        )
    """

    @classmethod
    def load(
        cls,
        base_path: str | Path,
        overrides: list[str | Path] | None = None,
        resolve_env: bool = True,
    ) -> dict[str, Any]:
        """
        Load the base config and optionally merge domain override files.

        Args:
            base_path:   Path to the primary platform YAML file.
            overrides:   Additional YAML files merged on top (in order).
            resolve_env: Whether to substitute ${VAR} env expressions.

        Returns:
            A plain dict representing the merged configuration.

        Raises:
            ConfigLoadError: If any file cannot be read or parsed.
        """
        merged: dict[str, Any] = cls._read_yaml(base_path)
        logger.debug("Loaded base config from '%s'.", base_path)

        for override_path in overrides or []:
            override_data = cls._read_yaml(override_path)
            merged = cls._deep_merge(merged, override_data)
            logger.debug("Merged override config from '%s'.", override_path)

        if resolve_env:
            merged = resolve_env_vars(merged)
            logger.debug("Environment variable resolution complete.")

        return merged

    @classmethod
    def load_domain(
        cls,
        domain_path: str | Path,
        resolve_env: bool = True,
    ) -> dict[str, Any]:
        """
        Load a single domain YAML file independently.

        Used to load domain configs that are nested under a 'domains' key
        inside the platform config, or standalone domain files.

        Args:
            domain_path: Path to the domain YAML file.
            resolve_env: Whether to substitute ${VAR} env expressions.

        Returns:
            A plain dict representing the domain configuration.
        """
        data = cls._read_yaml(domain_path)
        if resolve_env:
            data = resolve_env_vars(data)
        logger.debug("Loaded domain config from '%s'.", domain_path)
        return data

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_yaml(path: str | Path) -> dict[str, Any]:
        """Read and parse a single YAML file."""
        resolved_path = Path(path)
        if not resolved_path.exists():
            raise ConfigLoadError(
                f"Configuration file not found: '{resolved_path.resolve()}'. "
                f"Ensure the file exists before starting the platform."
            )
        try:
            with resolved_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            raise ConfigLoadError(
                f"Failed to parse YAML file '{resolved_path}': {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise ConfigLoadError(
                f"Config file '{resolved_path}' must be a YAML mapping (dict) "
                f"at the top level, got {type(data).__name__}."
            )
        return data

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively merge `override` into `base`.

        Rules:
            - Scalar values in `override` replace those in `base`.
            - Nested dicts are merged recursively.
            - Lists in `override` REPLACE (not extend) those in `base`.
              This keeps domain configs predictable.
        """
        result = copy.deepcopy(base)
        for key, override_value in override.items():
            base_value = result.get(key)
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = ConfigLoader._deep_merge(base_value, override_value)
            else:
                result[key] = copy.deepcopy(override_value)
        return result
