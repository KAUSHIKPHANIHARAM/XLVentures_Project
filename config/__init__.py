"""
config/__init__.py

Public API for the config module.

Every other module in the platform imports from here.
Nothing imports directly from config.loader, config.validator, etc.
This enforces clean module boundaries.

Example:
    from config import get_config, initialize
    from config import PlatformConfig, DomainConfig, AgentConfig
"""

from config.schemas import (
    AgentConfig,
    DatabaseConfig,
    DomainConfig,
    EmbeddingConfig,
    EntityConfig,
    EntityFieldConfig,
    KnowledgeSourceConfig,
    LLMConfig,
    LoggingConfig,
    PlatformConfig,
    ToolConfig,
    ToolParameterSchema,
    VectorDBConfig,
    WorkflowConfig,
    WorkflowEdge,
)
from config.settings import get_config, initialize, reset

__all__ = [
    # Settings
    "get_config",
    "initialize",
    "reset",
    # Top-level config model
    "PlatformConfig",
    # Infrastructure configs
    "LLMConfig",
    "EmbeddingConfig",
    "VectorDBConfig",
    "DatabaseConfig",
    "LoggingConfig",
    # Domain configs
    "DomainConfig",
    "AgentConfig",
    "ToolConfig",
    "ToolParameterSchema",
    "WorkflowConfig",
    "WorkflowEdge",
    "EntityConfig",
    "EntityFieldConfig",
    "KnowledgeSourceConfig",
]
