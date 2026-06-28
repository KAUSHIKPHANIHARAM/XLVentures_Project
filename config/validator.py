"""
config/validator.py

Validates raw configuration dictionaries against Pydantic schemas.

Responsibility:
    Accept a plain dict (from ConfigLoader) and return a fully-validated,
    typed PlatformConfig. If validation fails, raise a clear, actionable error.

Design:
    - Single public function: validate_platform_config().
    - Separates domain configs from the base platform config.
    - Reports all validation errors at once (not just the first one).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from config.schemas import DomainConfig, PlatformConfig

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration fails Pydantic schema validation."""


def validate_platform_config(raw: dict[str, Any]) -> PlatformConfig:
    """
    Validate a raw config dict and return a typed PlatformConfig.

    The raw dict may contain a 'domains' key whose values are each
    validated as DomainConfig objects independently before the outer
    PlatformConfig is assembled.

    Args:
        raw: Merged, env-resolved config dict from ConfigLoader.

    Returns:
        A frozen PlatformConfig instance.

    Raises:
        ConfigValidationError: With a human-readable message listing all errors.
    """
    logger.debug("Validating platform configuration.")

    # Validate individual domain configs first for clearer error reporting
    raw_domains: dict[str, Any] = raw.get("domains", {})
    validated_domains: dict[str, DomainConfig] = {}

    for domain_name, domain_data in raw_domains.items():
        try:
            validated_domains[domain_name] = DomainConfig.model_validate(domain_data)
            logger.debug("Domain config '%s' validated successfully.", domain_name)
        except ValidationError as exc:
            raise ConfigValidationError(
                f"Domain config '{domain_name}' is invalid:\n{_format_errors(exc)}"
            ) from exc

    # Inject validated domain objects back into the raw dict
    raw_with_typed_domains = {**raw, "domains": validated_domains}

    try:
        config = PlatformConfig.model_validate(raw_with_typed_domains)
    except ValidationError as exc:
        raise ConfigValidationError(
            f"Platform config is invalid:\n{_format_errors(exc)}"
        ) from exc

    logger.info(
        "Platform config validated. Environment='%s', Active domain='%s'.",
        config.environment,
        config.active_domain,
    )
    return config


def validate_domain_config(raw: dict[str, Any]) -> DomainConfig:
    """
    Validate a single raw domain config dict.

    Useful for loading standalone domain YAML files at runtime
    (e.g. hot-reloading a new domain without restarting).

    Args:
        raw: Domain config dict from ConfigLoader.load_domain().

    Returns:
        A frozen DomainConfig instance.

    Raises:
        ConfigValidationError: With a human-readable message.
    """
    try:
        domain = DomainConfig.model_validate(raw)
        logger.debug("Standalone domain config '%s' validated.", domain.name)
        return domain
    except ValidationError as exc:
        raise ConfigValidationError(
            f"Domain config is invalid:\n{_format_errors(exc)}"
        ) from exc


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_errors(exc: ValidationError) -> str:
    """Format Pydantic validation errors into a human-readable string."""
    lines = []
    for error in exc.errors():
        location = " → ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        lines.append(f"  [{location}] {message}")
    return "\n".join(lines)
