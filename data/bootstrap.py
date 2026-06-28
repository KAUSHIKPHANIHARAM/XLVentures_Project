"""
data/bootstrap.py

Data layer bootstrap — orchestrates DB init and seed data loading.

Called once at application startup. Ensures the database is ready
and populated with seed data before any agent or tool runs.

This is the only entry point the app/ module needs to call.

Usage:
    from data.bootstrap import bootstrap_data_layer
    bootstrap_data_layer(cfg)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from connectors.registry import register_connector
from data.seeder import DataSeeder
from utils.logging import get_logger

if TYPE_CHECKING:
    from config.schemas import PlatformConfig

logger = get_logger(__name__)


def bootstrap_data_layer(
    platform_config: "PlatformConfig",
    seed: bool = True,
    force_reseed: bool = False,
) -> None:
    """
    Initialize the data layer for all active domains.

    Steps:
        1. Register a connector for the active domain.
        2. Bootstrap tables (CREATE TABLE IF NOT EXISTS) via connector.
        3. Optionally seed the database with initial data.

    Args:
        platform_config: The validated platform configuration.
        seed:            If True, load seed data after creating tables.
        force_reseed:    If True, insert seed data even if records exist.
    """
    domain_config = platform_config.current_domain
    db_config = platform_config.database

    logger.info(
        "Bootstrapping data layer for domain '%s'.", domain_config.name
    )

    # Step 1: Register connector (this also runs bootstrap_domain + DDL)
    connector = register_connector(domain_config, db_config)

    # Step 2: Verify connectivity
    if not connector.health_check():
        raise RuntimeError(
            f"Database health check failed for domain '{domain_config.name}'. "
            f"Check your database connection string."
        )

    logger.info("Database connectivity verified.")

    # Step 3: Seed data
    if seed:
        seeder = DataSeeder(domain=domain_config.name)
        results = seeder.seed(force=force_reseed)
        if results:
            logger.info("Seed data loaded: %s", results)
        else:
            logger.info("No new seed data loaded (already seeded or no seed file).")

    logger.info(
        "Data layer bootstrap complete for domain '%s'.", domain_config.name
    )
