"""
models/registry.py

ModelRegistry — central store for all dynamically created Table objects.

After the DynamicTableFactory creates a Table, the ModelRegistry stores it
so any module can look it up by domain + entity type without repeating
the creation process.

Responsibilities:
    - Store Table objects keyed by (domain, entity_type).
    - Build all tables for a domain in one call (bootstrap step).
    - Create all tables in the database (DDL: CREATE TABLE IF NOT EXISTS).
    - Provide thread-safe lookup.

Design:
    - Singleton registry (module-level dict + lock).
    - bootstrap_domain() is called once at startup per domain.
    - get_table() is called frequently during query execution — must be fast.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from sqlalchemy import Engine, Table

from config.schemas import DomainConfig, EntityConfig
from models.base import get_engine, metadata
from models.factory import DynamicTableFactory

if TYPE_CHECKING:
    from config.schemas import DatabaseConfig

logger = logging.getLogger(__name__)

# In-memory registry: (domain_name, entity_type) → Table
_registry: dict[tuple[str, str], Table] = {}
_registry_lock = threading.Lock()


class TableNotFoundError(Exception):
    """Raised when a requested table is not in the registry."""


def bootstrap_domain(
    domain_config: DomainConfig,
    db_config: "DatabaseConfig",
    create_tables: bool = True,
) -> dict[str, Table]:
    """
    Build and register all SQLAlchemy Tables for a domain.

    Called once at platform startup for the active domain (and any
    additional domains that need tables). Idempotent — safe to call again.

    Args:
        domain_config:  The validated DomainConfig for the domain.
        db_config:      DatabaseConfig used to get/create the engine.
        create_tables:  If True, issue CREATE TABLE IF NOT EXISTS DDL.

    Returns:
        Dict of entity_type → Table for all entities in the domain.
    """
    domain_name = domain_config.name
    created: dict[str, Table] = {}

    with _registry_lock:
        for entity_config in domain_config.entities:
            key = (domain_name, entity_config.name)

            if key in _registry:
                logger.debug(
                    "Entity '%s' in domain '%s' already registered — skipping.",
                    entity_config.name,
                    domain_name,
                )
                created[entity_config.name] = _registry[key]
                continue

            table = DynamicTableFactory.create(entity_config)
            _registry[key] = table
            created[entity_config.name] = table

            logger.info(
                "Registered table '%s' for entity '%s' in domain '%s'.",
                entity_config.table_name,
                entity_config.name,
                domain_name,
            )

    if create_tables and created:
        engine = get_engine(db_config)
        _create_all_tables(engine)

    return created


def get_table(domain: str, entity_type: str) -> Table:
    """
    Retrieve a registered SQLAlchemy Table.

    Args:
        domain:      Domain name (e.g. 'customer_management').
        entity_type: Entity class name (e.g. 'Customer').

    Returns:
        The SQLAlchemy Table object.

    Raises:
        TableNotFoundError: If the table hasn't been registered yet.
    """
    key = (domain, entity_type)
    table = _registry.get(key)
    if table is None:
        available = [f"{d}/{e}" for (d, e) in _registry]
        raise TableNotFoundError(
            f"No table registered for domain='{domain}', entity='{entity_type}'. "
            f"Available: {available}. "
            f"Ensure bootstrap_domain() was called for this domain at startup."
        )
    return table


def list_registered_entities(domain: str | None = None) -> list[tuple[str, str]]:
    """
    List all registered (domain, entity_type) pairs.

    Args:
        domain: If provided, filter to this domain only.

    Returns:
        List of (domain, entity_type) tuples.
    """
    with _registry_lock:
        keys = list(_registry.keys())
    if domain:
        return [(d, e) for (d, e) in keys if d == domain]
    return keys


def get_entity_config_from_domain(
    domain_config: DomainConfig, entity_type: str
) -> EntityConfig:
    """
    Convenience: find an EntityConfig by entity_type name within a DomainConfig.

    Args:
        domain_config: The domain configuration.
        entity_type:   Entity class name (e.g. 'Customer').

    Returns:
        The matching EntityConfig.

    Raises:
        TableNotFoundError: If not found.
    """
    for entity in domain_config.entities:
        if entity.name == entity_type:
            return entity
    available = [e.name for e in domain_config.entities]
    raise TableNotFoundError(
        f"Entity '{entity_type}' not defined in domain '{domain_config.name}'. "
        f"Available entities: {available}"
    )


def reset_registry() -> None:
    """Clear the registry (for tests only)."""
    global _registry  # noqa: PLW0603
    with _registry_lock:
        _registry = {}
    logger.debug("Model registry reset.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _create_all_tables(engine: Engine) -> None:
    """Issue CREATE TABLE IF NOT EXISTS for all tables in MetaData."""
    try:
        metadata.create_all(engine, checkfirst=True)
        logger.info("Database DDL applied — all tables created/verified.")
    except Exception as exc:
        logger.error("Failed to create database tables: %s", exc)
        raise
