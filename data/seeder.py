"""
data/seeder.py

Database seed data loader.

Reads JSON seed files and inserts records via the connector layer.
Seeding is idempotent — it checks if data already exists before inserting.

Design:
    - Domain-agnostic: reads the domain name from the seed file structure.
    - Uses AbstractConnector (via registry) — never touches SQLAlchemy directly.
    - Skips individual records that fail (logs error) rather than aborting.
    - Idempotency: checks total record count; skips if table already has data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from connectors.registry import get_connector
from schemas.entity import EntityCreateRequest
from utils.logging import get_logger

logger = get_logger(__name__)

SEED_DIR = Path(__file__).parent / "seed"


class DataSeeder:
    """
    Loads seed data from JSON files and inserts records via the connector.

    Args:
        domain: The domain name to seed (e.g. 'customer_management').
    """

    def __init__(self, domain: str) -> None:
        self._domain = domain
        self._connector = get_connector(domain)

    def seed(self, force: bool = False) -> dict[str, int]:
        """
        Load and insert seed data for the domain.

        Args:
            force: If True, seed even if records already exist.
                   Default False (idempotent — skip if data present).

        Returns:
            Dict of entity_type → number of records inserted.
        """
        seed_file = SEED_DIR / f"{self._domain}.json"

        if not seed_file.exists():
            logger.warning(
                "No seed file found for domain '%s' at '%s'. Skipping.",
                self._domain,
                seed_file,
            )
            return {}

        with seed_file.open("r", encoding="utf-8") as fh:
            seed_data: dict[str, dict[str, list[dict]]] = json.load(fh)

        domain_data = seed_data.get(self._domain, {})
        if not domain_data:
            logger.warning("Seed file has no data for domain '%s'.", self._domain)
            return {}

        results: dict[str, int] = {}

        for entity_type, records in domain_data.items():
            inserted = self._seed_entity(entity_type, records, force)
            results[entity_type] = inserted

        total = sum(results.values())
        logger.info(
            "Seeding complete for domain '%s': %d total records inserted. "
            "Breakdown: %s",
            self._domain,
            total,
            results,
        )
        return results

    def _seed_entity(
        self,
        entity_type: str,
        records: list[dict[str, Any]],
        force: bool,
    ) -> int:
        """Seed a single entity type. Returns number of records inserted."""
        # Idempotency check
        if not force:
            existing = self._connector.get_all(entity_type, limit=1)
            if not existing.is_empty:
                logger.info(
                    "Entity '%s' already has data — skipping seed (use force=True to override).",
                    entity_type,
                )
                return 0

        inserted = 0
        for i, record_data in enumerate(records):
            try:
                request = EntityCreateRequest(
                    entity_type=entity_type,
                    domain=self._domain,
                    table_name=self._get_table_name(entity_type),
                    data=record_data,
                )
                self._connector.create(request)
                inserted += 1
            except Exception as exc:
                logger.error(
                    "Failed to insert %s record %d: %s | Data: %s",
                    entity_type,
                    i,
                    exc,
                    record_data,
                )

        logger.info(
            "Seeded %d/%d %s record(s) for domain '%s'.",
            inserted,
            len(records),
            entity_type,
            self._domain,
        )
        return inserted

    def _get_table_name(self, entity_type: str) -> str:
        """Look up table_name from connector's domain config."""
        entity_config = self._connector._get_entity_config(entity_type)
        return entity_config.table_name
