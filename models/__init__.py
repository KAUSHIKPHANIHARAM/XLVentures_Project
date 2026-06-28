"""
models/__init__.py

Public API for the models module.

Provides everything downstream modules need to work with the dynamic
data model layer without importing from internal submodules directly.

Usage:
    from models import bootstrap_domain, get_table, get_engine
    from models import DynamicTableFactory, TableNotFoundError
"""

from models.base import get_engine, metadata, reset_engine
from models.factory import DynamicTableFactory
from models.registry import (
    TableNotFoundError,
    bootstrap_domain,
    get_entity_config_from_domain,
    get_table,
    list_registered_entities,
    reset_registry,
)
from models.types import YAML_TYPE_MAP, resolve_column_type

__all__ = [
    # Engine / metadata
    "get_engine",
    "metadata",
    "reset_engine",
    # Factory
    "DynamicTableFactory",
    # Registry
    "bootstrap_domain",
    "get_table",
    "get_entity_config_from_domain",
    "list_registered_entities",
    "reset_registry",
    "TableNotFoundError",
    # Types
    "resolve_column_type",
    "YAML_TYPE_MAP",
]
