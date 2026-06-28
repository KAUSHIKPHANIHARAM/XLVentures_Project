"""
connectors/base.py

AbstractConnector — the data access contract for the entire platform.

All modules that need data (agents, tools, decision engine) depend on this
interface, never on SQLite, PostgreSQL, or any concrete implementation.
This enforces Dependency Inversion and makes the platform storage-agnostic.

Design:
    - Pure abstract base class (ABC) — no implementation here.
    - Every method is domain-agnostic: entity_type is a string, data is a dict.
    - Connectors are domain-scoped: one connector instance per domain.
    - The DomainConfig is injected at construction so the connector knows
      entity schemas, primary keys, and searchable fields — from YAML, not code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from config.schemas import DomainConfig
from schemas.entity import (
    EntityCreateRequest,
    EntityRecord,
    EntitySearchResult,
    EntityUpdateRequest,
)


class AbstractConnector(ABC):
    """
    Abstract interface for all data source connectors.

    Concrete implementations include SQLiteConnector, PostgresConnector,
    RestApiConnector, etc. All share this same interface.

    Args:
        domain_config: The domain configuration containing entity schemas.
    """

    def __init__(self, domain_config: DomainConfig) -> None:
        self._domain_config = domain_config
        self._domain = domain_config.name

    @property
    def domain(self) -> str:
        """The domain this connector serves."""
        return self._domain

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @abstractmethod
    def get_by_id(
        self,
        entity_type: str,
        entity_id: str | int,
    ) -> EntityRecord | None:
        """
        Retrieve a single entity record by its primary key.

        Args:
            entity_type: Entity class name (e.g. 'Customer').
            entity_id:   Primary key value.

        Returns:
            EntityRecord if found, None if not found.
        """

    @abstractmethod
    def get_all(
        self,
        entity_type: str,
        limit: int = 50,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> EntitySearchResult:
        """
        Retrieve all records for an entity type with pagination.

        Args:
            entity_type: Entity class name.
            limit:       Maximum records to return.
            offset:      Number of records to skip (for pagination).
            order_by:    Field name to sort by.
            descending:  If True, sort descending.

        Returns:
            EntitySearchResult with all matching records.
        """

    @abstractmethod
    def search(
        self,
        entity_type: str,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> EntitySearchResult:
        """
        Full-text search across searchable fields with optional exact filters.

        Searches across all fields marked searchable=true in the entity config.
        Filters apply exact matches on any field.

        Args:
            entity_type: Entity class name.
            query:       Search string (matched against searchable fields).
            filters:     Dict of field_name → value for exact-match filtering.
            limit:       Maximum records to return.

        Returns:
            EntitySearchResult with matching records.
        """

    @abstractmethod
    def filter_by(
        self,
        entity_type: str,
        filters: dict[str, Any],
        limit: int = 50,
        order_by: str | None = None,
        descending: bool = False,
    ) -> EntitySearchResult:
        """
        Retrieve records matching exact field values.

        Args:
            entity_type: Entity class name.
            filters:     Dict of field_name → value to match exactly.
            limit:       Maximum records to return.
            order_by:    Field name to sort by.
            descending:  If True, sort descending.

        Returns:
            EntitySearchResult with matching records.
        """

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @abstractmethod
    def create(self, request: EntityCreateRequest) -> EntityRecord:
        """
        Insert a new entity record.

        Args:
            request: EntityCreateRequest with field data.

        Returns:
            The created EntityRecord with its assigned primary key.

        Raises:
            ConnectorWriteError: If the insert fails.
        """

    @abstractmethod
    def update(self, request: EntityUpdateRequest) -> EntityRecord:
        """
        Update fields on an existing entity record.

        Args:
            request: EntityUpdateRequest specifying which fields to change.

        Returns:
            The updated EntityRecord.

        Raises:
            ConnectorWriteError: If the update fails or entity not found.
        """

    @abstractmethod
    def delete(self, entity_type: str, entity_id: str | int) -> bool:
        """
        Delete an entity record by primary key.

        Args:
            entity_type: Entity class name.
            entity_id:   Primary key value.

        Returns:
            True if deleted, False if not found.
        """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def health_check(self) -> bool:
        """
        Verify the connector can reach its data source.

        Returns:
            True if healthy, False otherwise.
        """

    def _get_entity_config(self, entity_type: str):
        """Helper: retrieve EntityConfig for a given entity type."""
        for entity in self._domain_config.entities:
            if entity.name == entity_type:
                return entity
        raise ConnectorEntityError(
            f"Entity '{entity_type}' not defined in domain '{self._domain}'. "
            f"Available: {[e.name for e in self._domain_config.entities]}"
        )

    def _get_searchable_fields(self, entity_type: str) -> list[str]:
        """Return field names marked searchable=true for an entity."""
        cfg = self._get_entity_config(entity_type)
        return [name for name, f in cfg.fields.items() if f.searchable]


# ---------------------------------------------------------------------------
# Connector-specific exceptions
# ---------------------------------------------------------------------------


class ConnectorError(Exception):
    """Base exception for all connector errors."""


class ConnectorEntityError(ConnectorError):
    """Raised when an entity type is not defined in the domain config."""


class ConnectorWriteError(ConnectorError):
    """Raised when a write operation (create/update/delete) fails."""


class ConnectorNotFoundError(ConnectorError):
    """Raised when a required entity record is not found."""
