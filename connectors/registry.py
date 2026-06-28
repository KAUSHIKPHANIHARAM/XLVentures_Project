"""
connectors/registry.py

ConnectorRegistry — maps domain names to their active connector instances.

At startup, the platform instantiates one connector per domain and registers
it here. All agents and tools look up their connector by domain name.

Design:
    - Singleton registry (module-level dict + lock).
    - Supports multiple connector types (SQLite, Postgres, REST…) keyed by
      the 'provider' field in DatabaseConfig.
    - get_connector() raises clearly if a domain hasn't been registered.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from connectors.base import AbstractConnector, ConnectorError

if TYPE_CHECKING:
    from config.schemas import DatabaseConfig, DomainConfig

logger = logging.getLogger(__name__)

_connectors: dict[str, AbstractConnector] = {}
_lock = threading.Lock()


class ConnectorNotRegisteredError(ConnectorError):
    """Raised when get_connector() is called for an unregistered domain."""


def register_connector(
    domain_config: "DomainConfig",
    db_config: "DatabaseConfig",
) -> AbstractConnector:
    """
    Instantiate and register the appropriate connector for a domain.

    The connector type is determined by db_config.provider:
        - 'sqlite'   → SQLiteConnector
        - 'postgres' → (future) PostgresConnector
        - etc.

    Args:
        domain_config: Domain configuration.
        db_config:     Database configuration.

    Returns:
        The registered AbstractConnector instance.

    Raises:
        ConnectorError: If the provider is unsupported.
    """
    domain_name = domain_config.name

    with _lock:
        if domain_name in _connectors:
            logger.debug(
                "Connector for domain '%s' already registered — returning existing.",
                domain_name,
            )
            return _connectors[domain_name]

        connector = _create_connector(domain_config, db_config)
        _connectors[domain_name] = connector

        logger.info(
            "Registered %s connector for domain '%s'.",
            db_config.provider,
            domain_name,
        )
        return connector


def get_connector(domain: str) -> AbstractConnector:
    """
    Retrieve the registered connector for a domain.

    Args:
        domain: Domain name (e.g. 'customer_management').

    Returns:
        The AbstractConnector instance for this domain.

    Raises:
        ConnectorNotRegisteredError: If the domain hasn't been registered.
    """
    connector = _connectors.get(domain)
    if connector is None:
        available = list(_connectors.keys())
        raise ConnectorNotRegisteredError(
            f"No connector registered for domain '{domain}'. "
            f"Available domains: {available}. "
            f"Ensure register_connector() was called at startup."
        )
    return connector


def reset_registry() -> None:
    """Clear the connector registry (for tests only)."""
    global _connectors  # noqa: PLW0603
    with _lock:
        _connectors = {}
    logger.debug("Connector registry reset.")


# ---------------------------------------------------------------------------
# Private factory
# ---------------------------------------------------------------------------


def _create_connector(
    domain_config: "DomainConfig",
    db_config: "DatabaseConfig",
) -> AbstractConnector:
    """Instantiate the correct connector based on db_config.provider."""
    provider = db_config.provider.lower()

    if provider == "sqlite":
        from connectors.sqlite.connector import SQLiteConnector
        return SQLiteConnector(domain_config, db_config)

    # Extensibility point — add new providers here:
    # if provider == "postgres":
    #     from connectors.postgres.connector import PostgresConnector
    #     return PostgresConnector(domain_config, db_config)

    raise ConnectorError(
        f"Unsupported database provider '{provider}'. "
        f"Supported: ['sqlite']. Add new providers in connectors/registry.py."
    )
