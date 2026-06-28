"""
models/factory.py

DynamicTableFactory — builds SQLAlchemy Table objects from EntityConfig.

This is the core of the config-driven data layer. Instead of writing
a Python class for each entity (Customer, Employee, Invoice…), we read
the entity definition from the domain YAML and construct the Table
object at runtime.

Benefits:
    - New entity type = add YAML block, no Python needed.
    - Works identically for Customer, Employee, Invoice, PO, etc.
    - Handles primary keys, indexes, nullable columns, and type mapping
      all from config.

Design:
    - DynamicTableFactory is a pure factory — it creates Table objects
      but does not store them. Storage is the ModelRegistry's job.
    - Tables are registered in the shared MetaData (from models.base),
      which makes them visible to create_all() and foreign key resolution.
"""

from __future__ import annotations

import logging

from sqlalchemy import Column, Index, Integer, Table

from config.schemas import EntityConfig, EntityFieldConfig
from models.base import metadata
from models.types import resolve_column_type

logger = logging.getLogger(__name__)


class DynamicTableFactory:
    """
    Builds SQLAlchemy Table objects from EntityConfig definitions.

    Usage:
        table = DynamicTableFactory.create(entity_config)
        # 'table' is now a SQLAlchemy Table object, registered in MetaData.
    """

    @classmethod
    def create(cls, entity_config: EntityConfig) -> Table:
        """
        Build a SQLAlchemy Table from an EntityConfig.

        If a table with this name already exists in the shared MetaData,
        the existing table is returned (idempotent — safe to call multiple times).

        Args:
            entity_config: Validated EntityConfig loaded from domain YAML.

        Returns:
            A SQLAlchemy Table object registered in the shared MetaData.
        """
        table_name = entity_config.table_name

        # Idempotency: return existing table if already registered
        if table_name in metadata.tables:
            logger.debug(
                "Table '%s' already registered — returning existing.", table_name
            )
            return metadata.tables[table_name]

        columns = cls._build_columns(entity_config)
        indexes = cls._build_indexes(entity_config, table_name)

        table = Table(table_name, metadata, *columns, *indexes)

        logger.info(
            "Dynamic table created: '%s' with %d column(s) for entity '%s'.",
            table_name,
            len(columns),
            entity_config.name,
        )
        return table

    # ------------------------------------------------------------------
    # Private: column builders
    # ------------------------------------------------------------------

    @classmethod
    def _build_columns(cls, entity_config: EntityConfig) -> list[Column]:
        """Build the ordered list of SQLAlchemy Column objects."""
        columns: list[Column] = []

        for field_name, field_config in entity_config.fields.items():
            column = cls._build_column(
                field_name=field_name,
                field_config=field_config,
                is_primary_key=(field_name == entity_config.primary_key),
            )
            columns.append(column)

        return columns

    @staticmethod
    def _build_column(
        field_name: str,
        field_config: EntityFieldConfig,
        is_primary_key: bool,
    ) -> Column:
        """Build a single SQLAlchemy Column from an EntityFieldConfig."""

        if is_primary_key and field_config.type in ("integer", "int"):
            # Auto-increment integer PK — standard for SQLite
            return Column(
                field_name,
                Integer,
                primary_key=True,
                autoincrement=True,
                comment=field_config.description or None,
            )

        col_type = resolve_column_type(field_config.type)
        nullable = not field_config.required

        return Column(
            field_name,
            col_type,
            primary_key=is_primary_key,
            nullable=nullable,
            comment=field_config.description or None,
        )

    @staticmethod
    def _build_indexes(entity_config: EntityConfig, table_name: str) -> list[Index]:
        """Build SQLAlchemy Index objects for fields marked indexed=true."""
        indexes: list[Index] = []

        indexed_fields = [
            field_name
            for field_name, field_cfg in entity_config.fields.items()
            if field_cfg.indexed and field_name != entity_config.primary_key
        ]

        for field_name in indexed_fields:
            index_name = f"ix_{table_name}_{field_name}"
            indexes.append(Index(index_name, field_name))
            logger.debug("Index defined: '%s' on '%s.%s'.", index_name, table_name, field_name)

        return indexes
