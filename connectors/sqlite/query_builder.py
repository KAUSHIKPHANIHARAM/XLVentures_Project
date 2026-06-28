"""
connectors/sqlite/query_builder.py

SQLAlchemy Core query builder for dynamic entity tables.

Translates high-level connector operations (search, filter, get_all)
into SQLAlchemy SELECT statements using the dynamic Table objects from
the model registry. Never writes raw SQL strings.

Design:
    - Stateless class — all methods are static.
    - Uses SQLAlchemy Core API (not ORM) — no class mapping needed.
    - Search uses SQL LIKE across all searchable fields (OR logic).
    - Filters use exact equality (AND logic).
    - Handles type coercion for numeric comparisons.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Table, and_, asc, desc, or_, select, text
from sqlalchemy.sql import Select

from config.schemas import EntityConfig

logger = logging.getLogger(__name__)


class QueryBuilder:
    """
    Builds SQLAlchemy Core SELECT statements for dynamic entity tables.
    """

    @staticmethod
    def build_get_by_id(
        table: Table,
        entity_config: EntityConfig,
        entity_id: str | int,
    ) -> Select:
        """Build a SELECT ... WHERE id = :id query."""
        pk_col = table.c[entity_config.primary_key]
        return select(table).where(pk_col == entity_id)

    @staticmethod
    def build_get_all(
        table: Table,
        entity_config: EntityConfig,
        limit: int,
        offset: int,
        order_by: str | None = None,
        descending: bool = False,
    ) -> Select:
        """Build a paginated SELECT * query with optional ordering."""
        stmt = select(table)

        if order_by and order_by in table.c:
            col = table.c[order_by]
            stmt = stmt.order_by(desc(col) if descending else asc(col))
        else:
            # Default: order by primary key ascending
            stmt = stmt.order_by(asc(table.c[entity_config.primary_key]))

        return stmt.limit(limit).offset(offset)

    @staticmethod
    def build_search(
        table: Table,
        entity_config: EntityConfig,
        query: str,
        filters: dict[str, Any] | None,
        limit: int,
    ) -> Select:
        """
        Build a search SELECT with LIKE across searchable fields + exact filters.

        Search logic:
            WHERE (field1 LIKE '%query%' OR field2 LIKE '%query%' ...)
              AND (filter1 = val1 AND filter2 = val2 ...)
        """
        conditions = []

        # --- Text search across searchable fields ---
        searchable_fields = [
            name for name, f in entity_config.fields.items() if f.searchable
        ]

        if query.strip() and searchable_fields:
            like_pattern = f"%{query.strip()}%"
            like_conditions = [
                table.c[field_name].like(like_pattern)
                for field_name in searchable_fields
                if field_name in table.c
            ]
            if like_conditions:
                conditions.append(or_(*like_conditions))

        # --- Exact-match filters ---
        if filters:
            filter_conditions = QueryBuilder._build_filter_conditions(
                table, entity_config, filters
            )
            conditions.extend(filter_conditions)

        stmt = select(table)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Order by primary key for consistent results
        stmt = stmt.order_by(asc(table.c[entity_config.primary_key]))

        return stmt.limit(limit)

    @staticmethod
    def build_filter_by(
        table: Table,
        entity_config: EntityConfig,
        filters: dict[str, Any],
        limit: int,
        order_by: str | None = None,
        descending: bool = False,
    ) -> Select:
        """Build a SELECT with exact-match filters only (no LIKE search)."""
        conditions = QueryBuilder._build_filter_conditions(table, entity_config, filters)
        stmt = select(table)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        if order_by and order_by in table.c:
            col = table.c[order_by]
            stmt = stmt.order_by(desc(col) if descending else asc(col))
        else:
            stmt = stmt.order_by(asc(table.c[entity_config.primary_key]))

        return stmt.limit(limit)

    @staticmethod
    def _build_filter_conditions(
        table: Table,
        entity_config: EntityConfig,
        filters: dict[str, Any],
    ) -> list:
        """Build AND conditions for exact-match filters."""
        conditions = []
        for field_name, value in filters.items():
            if field_name not in table.c:
                logger.warning(
                    "Filter field '%s' does not exist in table '%s' — skipping.",
                    field_name,
                    table.name,
                )
                continue
            if value is None:
                conditions.append(table.c[field_name].is_(None))
            else:
                conditions.append(table.c[field_name] == value)
        return conditions
