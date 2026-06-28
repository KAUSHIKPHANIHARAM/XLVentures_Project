"""
connectors/sqlite/connector.py

SQLiteConnector — concrete implementation of AbstractConnector for SQLite.

Uses:
    - SQLAlchemy Core for query execution (via dynamic tables from models/)
    - QueryBuilder for constructing SELECT statements
    - models.registry.get_table() to resolve Table objects by entity_type

Design:
    - One SQLiteConnector instance per domain (injected by the registry module).
    - All reads are scoped to the domain's entity tables.
    - Row results are converted to EntityRecord via _row_to_record().
    - Write operations use SQLAlchemy Core insert/update/delete.
    - Thread-safe: SQLAlchemy connection pool handles concurrency.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, insert, update
from sqlalchemy.engine import Engine, Row

from config.schemas import DatabaseConfig, DomainConfig, EntityConfig
from connectors.base import (
    AbstractConnector,
    ConnectorNotFoundError,
    ConnectorWriteError,
)
from connectors.sqlite.query_builder import QueryBuilder
from models.base import get_engine
from models.registry import bootstrap_domain, get_table
from schemas.entity import (
    EntityCreateRequest,
    EntityRecord,
    EntitySearchResult,
    EntityUpdateRequest,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class SQLiteConnector(AbstractConnector):
    """
    SQLite implementation of AbstractConnector using SQLAlchemy Core.

    Args:
        domain_config: Domain configuration (entities, fields, keys).
        db_config:     Database config (connection string, pool size).
    """

    def __init__(self, domain_config: DomainConfig, db_config: DatabaseConfig) -> None:
        super().__init__(domain_config)
        self._db_config = db_config
        self._engine: Engine = get_engine(db_config)

        # Bootstrap ensures all tables exist in the DB
        bootstrap_domain(domain_config, db_config, create_tables=True)
        logger.info(
            "SQLiteConnector initialized for domain '%s'.", domain_config.name
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_by_id(
        self, entity_type: str, entity_id: str | int
    ) -> EntityRecord | None:
        entity_config = self._get_entity_config(entity_type)
        table = get_table(self._domain, entity_type)
        stmt = QueryBuilder.build_get_by_id(table, entity_config, entity_id)

        with self._engine.connect() as conn:
            row = conn.execute(stmt).fetchone()

        if row is None:
            return None

        return self._row_to_record(row, entity_config, table)

    def get_all(
        self,
        entity_type: str,
        limit: int = 50,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> EntitySearchResult:
        entity_config = self._get_entity_config(entity_type)
        table = get_table(self._domain, entity_type)
        stmt = QueryBuilder.build_get_all(
            table, entity_config, limit, offset, order_by, descending
        )

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        records = [self._row_to_record(r, entity_config, table) for r in rows]

        return EntitySearchResult(
            entity_type=entity_type,
            domain=self._domain,
            query="*",
            records=records,
            total_found=len(records),
        )

    def search(
        self,
        entity_type: str,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> EntitySearchResult:
        entity_config = self._get_entity_config(entity_type)
        table = get_table(self._domain, entity_type)
        stmt = QueryBuilder.build_search(table, entity_config, query, filters, limit)

        logger.debug(
            "Search entity='%s' query='%s' filters=%s limit=%d",
            entity_type, query, filters, limit
        )

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        records = [self._row_to_record(r, entity_config, table) for r in rows]

        return EntitySearchResult(
            entity_type=entity_type,
            domain=self._domain,
            query=query,
            records=records,
            total_found=len(records),
            filters_applied=filters or {},
        )

    def filter_by(
        self,
        entity_type: str,
        filters: dict[str, Any],
        limit: int = 50,
        order_by: str | None = None,
        descending: bool = False,
    ) -> EntitySearchResult:
        entity_config = self._get_entity_config(entity_type)
        table = get_table(self._domain, entity_type)
        stmt = QueryBuilder.build_filter_by(
            table, entity_config, filters, limit, order_by, descending
        )

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        records = [self._row_to_record(r, entity_config, table) for r in rows]

        return EntitySearchResult(
            entity_type=entity_type,
            domain=self._domain,
            query="",
            records=records,
            total_found=len(records),
            filters_applied=filters,
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, request: EntityCreateRequest) -> EntityRecord:
        entity_config = self._get_entity_config(request.entity_type)
        table = get_table(self._domain, request.entity_type)

        stmt = insert(table).values(**request.data)

        try:
            with self._engine.begin() as conn:
                result = conn.execute(stmt)
                new_id = result.inserted_primary_key[0]
        except Exception as exc:
            raise ConnectorWriteError(
                f"Failed to create {request.entity_type}: {exc}"
            ) from exc

        # Fetch and return the created record
        created = self.get_by_id(request.entity_type, new_id)
        if created is None:
            raise ConnectorWriteError(
                f"Created {request.entity_type} with id={new_id} but could not retrieve it."
            )

        logger.info(
            "Created %s id=%s in domain '%s'.", request.entity_type, new_id, self._domain
        )
        return created

    def update(self, request: EntityUpdateRequest) -> EntityRecord:
        entity_config = self._get_entity_config(request.entity_type)
        table = get_table(self._domain, request.entity_type)
        pk_col = table.c[entity_config.primary_key]

        stmt = (
            update(table)
            .where(pk_col == request.entity_id)
            .values(**request.updates)
        )

        try:
            with self._engine.begin() as conn:
                result = conn.execute(stmt)
                if result.rowcount == 0:
                    raise ConnectorNotFoundError(
                        f"{request.entity_type} id={request.entity_id} not found."
                    )
        except ConnectorNotFoundError:
            raise
        except Exception as exc:
            raise ConnectorWriteError(
                f"Failed to update {request.entity_type} id={request.entity_id}: {exc}"
            ) from exc

        updated = self.get_by_id(request.entity_type, request.entity_id)
        logger.info(
            "Updated %s id=%s fields=%s.",
            request.entity_type, request.entity_id, list(request.updates.keys())
        )
        return updated  # type: ignore[return-value]

    def delete(self, entity_type: str, entity_id: str | int) -> bool:
        entity_config = self._get_entity_config(entity_type)
        table = get_table(self._domain, entity_type)
        pk_col = table.c[entity_config.primary_key]

        stmt = delete(table).where(pk_col == entity_id)

        with self._engine.begin() as conn:
            result = conn.execute(stmt)

        deleted = result.rowcount > 0
        if deleted:
            logger.info("Deleted %s id=%s.", entity_type, entity_id)
        else:
            logger.warning("%s id=%s not found — nothing deleted.", entity_type, entity_id)
        return deleted

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Ping the database to verify connectivity."""
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.error("SQLiteConnector health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _row_to_record(
        self,
        row: Row,
        entity_config: EntityConfig,
        table: Any,
    ) -> EntityRecord:
        """Convert a SQLAlchemy Row to an EntityRecord."""
        row_dict = dict(row._mapping)
        pk_value = row_dict.get(entity_config.primary_key, "")
        display_value = str(row_dict.get(entity_config.display_name_field, pk_value))

        return EntityRecord(
            entity_type=entity_config.name,
            entity_id=str(pk_value),
            domain=self._domain,
            table_name=entity_config.table_name,
            data=row_dict,
            display_name=display_value,
            source="database",
        )
