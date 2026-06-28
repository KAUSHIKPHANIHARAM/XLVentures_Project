"""
models/base.py

SQLAlchemy MetaData and engine management for the platform.

Provides the shared MetaData object used across all dynamic table
definitions, and the engine factory that creates the database connection
from DatabaseConfig.

Design:
    - A single MetaData instance is shared — required for foreign keys
      and consistent DDL operations across tables.
    - The engine is created lazily and cached (thread-safe).
    - Supports SQLite (hackathon) and is extensible to PostgreSQL/MySQL
      by changing the connection_string in platform.yaml — zero code change.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    from config.schemas import DatabaseConfig

logger = logging.getLogger(__name__)

# Shared metadata object — all dynamic tables are registered here
metadata = MetaData()

_engine: Engine | None = None
_engine_lock = threading.Lock()


def get_engine(db_config: "DatabaseConfig") -> Engine:
    """
    Return the cached SQLAlchemy engine, creating it on first call.

    Args:
        db_config: DatabaseConfig from the platform settings.

    Returns:
        A configured SQLAlchemy Engine instance.
    """
    global _engine  # noqa: PLW0603

    with _engine_lock:
        if _engine is not None:
            return _engine

        connection_string = db_config.connection_string

        # Normalise SQLite path prefix
        if db_config.provider == "sqlite" and not connection_string.startswith("sqlite"):
            connection_string = f"sqlite:///{connection_string}"

        # Ensure the data directory exists (SQLite cannot create parent dirs)
        if db_config.provider == "sqlite":
            raw_path = connection_string.replace("sqlite:///", "")
            Path(raw_path).parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Creating database engine. Provider='%s'.", db_config.provider
        )

        _engine = create_engine(
            connection_string,
            echo=db_config.echo_sql,
            pool_size=db_config.pool_size if db_config.provider != "sqlite" else 1,
            # SQLite: enable WAL mode for better concurrent read performance
            connect_args={"check_same_thread": False} if db_config.provider == "sqlite" else {},
        )

        # Enable SQLite foreign key enforcement (off by default in SQLite)
        if db_config.provider == "sqlite":
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

        logger.debug("Database engine created for '%s'.", connection_string)
        return _engine


def reset_engine() -> None:
    """Dispose of the cached engine (for use in tests only)."""
    global _engine  # noqa: PLW0603
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
            _engine = None
    logger.debug("Database engine reset.")
