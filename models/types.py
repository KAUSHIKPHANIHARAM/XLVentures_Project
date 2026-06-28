"""
models/types.py

Mapping from YAML config type names to SQLAlchemy column types.

The domain YAML declares entity fields with simple type strings
('string', 'integer', 'float', etc.). This module translates those
strings into concrete SQLAlchemy Column type objects.

Design:
    - Pure mapping — no state, no side effects.
    - Extensible: add new type aliases to YAML_TYPE_MAP as needed.
    - Unknown types fall back to Text with a warning rather than crashing,
      so a single misconfigured field doesn't prevent the entire table from loading.
"""

from __future__ import annotations

import logging

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.types import TypeEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type mapping: YAML type string → SQLAlchemy column type factory
# ---------------------------------------------------------------------------

YAML_TYPE_MAP: dict[str, type[TypeEngine]] = {
    # String variants
    "str": String,
    "string": String,
    "varchar": String,
    "char": String,
    # Integer variants
    "int": Integer,
    "integer": Integer,
    "bigint": Integer,
    "smallint": Integer,
    # Float / decimal variants
    "float": Float,
    "double": Float,
    "decimal": Float,
    "number": Float,
    # Boolean
    "bool": Boolean,
    "boolean": Boolean,
    # Long text (store as TEXT in SQLite)
    "text": Text,
    "longtext": Text,
    "clob": Text,
    # Temporal — stored as ISO-8601 strings (SQLite has no native datetime)
    "date": String,
    "datetime": String,
    "timestamp": String,
    "time": String,
    # JSON — stored as serialised string in SQLite
    "json": Text,
    "dict": Text,
    "list": Text,
}


def resolve_column_type(yaml_type: str) -> TypeEngine:
    """
    Resolve a YAML type string to a SQLAlchemy TypeEngine instance.

    Args:
        yaml_type: Type string from the domain YAML (e.g. 'string', 'integer').

    Returns:
        A SQLAlchemy TypeEngine instance (e.g. String(), Integer()).
    """
    normalised = yaml_type.lower().strip()
    column_type_cls = YAML_TYPE_MAP.get(normalised)

    if column_type_cls is None:
        logger.warning(
            "Unknown YAML type '%s' — falling back to Text. "
            "Add it to models/types.py YAML_TYPE_MAP if intentional.",
            yaml_type,
        )
        return Text()

    # String type gets a generous length for SQLite compatibility
    if column_type_cls is String:
        return String(length=1024)

    return column_type_cls()
