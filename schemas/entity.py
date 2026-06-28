"""
schemas/entity.py

Runtime models for domain entity data.

These models are domain-agnostic wrappers around structured data retrieved
from the connector layer (SQLite). They carry the entity's field values
as a generic dict so the same model works for Customer, Employee, Invoice,
or any other entity type defined in a domain YAML.

Design:
    - EntityRecord wraps raw DB row data with provenance metadata.
    - EntitySearchResult groups multiple records from a search query.
    - FieldValue provides type-safe access to individual entity fields.
    - No domain-specific field names appear in these models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core entity models
# ---------------------------------------------------------------------------


class EntityRecord(BaseModel):
    """
    A single entity record retrieved from the data layer.

    Wraps the raw field values (as a dict) with metadata about what
    entity type this is, which domain it belongs to, and where it came from.

    Example usage for a Customer entity:
        EntityRecord(
            entity_type="Customer",
            entity_id="42",
            domain="customer_management",
            data={"full_name": "Jane Doe", "email": "jane@acme.com", ...}
        )
    """

    entity_type: str = Field(
        description="Entity class name as defined in the domain config (e.g. 'Customer')."
    )
    entity_id: str = Field(
        description="String representation of the primary key value."
    )
    domain: str = Field(description="Domain this entity belongs to.")
    table_name: str = Field(
        description="Database table this entity was retrieved from."
    )
    data: dict[str, Any] = Field(
        description="Raw field values keyed by field name.",
        default_factory=dict,
    )
    display_name: str = Field(
        default="",
        description="Human-readable label for this entity (from display_name_field config).",
    )
    source: str = Field(
        default="database",
        description="Data source: 'database', 'cache', 'seed'.",
    )
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def get_field(self, field_name: str, default: Any = None) -> Any:
        """Safely retrieve a field value by name."""
        return self.data.get(field_name, default)

    def to_summary_dict(self, fields: list[str] | None = None) -> dict[str, Any]:
        """
        Return a subset of fields for summarised display.

        Args:
            fields: List of field names to include. If None, returns all.

        Returns:
            Dict of field_name -> value for the requested fields.
        """
        if fields is None:
            return dict(self.data)
        return {f: self.data.get(f) for f in fields}


class EntitySearchResult(BaseModel, frozen=True):
    """
    The result of a search query against the entity data layer.

    Groups multiple EntityRecord objects with query provenance.
    """

    entity_type: str
    domain: str
    query: str = Field(description="The search query that produced these results.")
    records: list[EntityRecord] = Field(default_factory=list)
    total_found: int = Field(default=0)
    filters_applied: dict[str, Any] = Field(
        default_factory=dict,
        description="Any filters that were applied to the search.",
    )
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def is_empty(self) -> bool:
        return len(self.records) == 0

    @property
    def first(self) -> EntityRecord | None:
        return self.records[0] if self.records else None


class EntityUpdateRequest(BaseModel, frozen=True):
    """
    A request to update fields on an existing entity record.

    The connector layer translates this into a SQL UPDATE statement.
    Never contains the primary key in 'updates' — it's in 'entity_id'.
    """

    entity_type: str
    entity_id: str
    domain: str
    table_name: str
    updates: dict[str, Any] = Field(
        description="Map of field_name -> new_value for fields to update."
    )
    updated_by: str | None = Field(
        default=None,
        description="User or agent ID responsible for this update (audit trail).",
    )
    reason: str = Field(
        default="",
        description="Human-readable reason for the update (audit trail).",
    )


class EntityCreateRequest(BaseModel, frozen=True):
    """
    A request to create a new entity record.

    The connector layer translates this into a SQL INSERT statement.
    """

    entity_type: str
    domain: str
    table_name: str
    data: dict[str, Any] = Field(
        description="Field values for the new entity record."
    )
    created_by: str | None = Field(default=None)
