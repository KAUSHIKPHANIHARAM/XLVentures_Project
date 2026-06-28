"""
connectors/__init__.py

Public API for the connectors module.

Usage:
    from connectors import AbstractConnector, register_connector, get_connector
    from connectors import SQLiteConnector
    from connectors import ConnectorError, ConnectorNotFoundError
"""

from connectors.base import (
    AbstractConnector,
    ConnectorEntityError,
    ConnectorError,
    ConnectorNotFoundError,
    ConnectorWriteError,
)
from connectors.registry import (
    ConnectorNotRegisteredError,
    get_connector,
    register_connector,
    reset_registry,
)
from connectors.sqlite import SQLiteConnector

__all__ = [
    # Interface
    "AbstractConnector",
    # Exceptions
    "ConnectorError",
    "ConnectorEntityError",
    "ConnectorWriteError",
    "ConnectorNotFoundError",
    "ConnectorNotRegisteredError",
    # Registry
    "register_connector",
    "get_connector",
    "reset_registry",
    # Implementations
    "SQLiteConnector",
]
