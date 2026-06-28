"""
config/schemas.py

Pydantic validation schemas for all platform configuration sections.

These models define the contract between YAML configuration files and
the rest of the platform. Every module that reads config trusts these
validated types — raw dicts never leave this layer.

Design:
    - All models are immutable (frozen=True) after load.
    - Optional fields use sensible defaults so minimal YAML is needed.
    - Models are composable: PlatformConfig aggregates all sub-configs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Infrastructure configs
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel, frozen=True):
    """Configuration for the Large Language Model provider."""

    provider: str = Field(default="openai", description="LLM provider name.")
    model: str = Field(default="gpt-4o", description="Model identifier.")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    api_key_env: str = Field(
        default="OPENAI_API_KEY",
        description="Name of the environment variable holding the API key.",
    )
    timeout_seconds: int = Field(default=60, gt=0)
    max_retries: int = Field(default=3, ge=0)


class EmbeddingConfig(BaseModel, frozen=True):
    """Configuration for the embedding model."""

    provider: str = Field(default="openai")
    model: str = Field(default="text-embedding-3-small")
    api_key_env: str = Field(default="OPENAI_API_KEY")
    dimensions: int = Field(default=1536, gt=0)


class VectorDBConfig(BaseModel, frozen=True):
    """Configuration for the ChromaDB vector store."""

    provider: str = Field(default="chromadb")
    persist_directory: str = Field(default="./data/vectordb")
    collection_prefix: str = Field(
        default="platform",
        description="Prefix applied to all collection names.",
    )
    distance_metric: str = Field(default="cosine")
    top_k: int = Field(default=5, gt=0)


class DatabaseConfig(BaseModel, frozen=True):
    """Configuration for the relational database (SQLite for hackathon)."""

    provider: str = Field(default="sqlite")
    connection_string: str = Field(default="./data/platform.db")
    echo_sql: bool = Field(default=False)
    pool_size: int = Field(default=5, gt=0)


class LoggingConfig(BaseModel, frozen=True):
    """Configuration for platform-wide logging."""

    level: str = Field(default="INFO")
    format: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    file_path: str | None = Field(
        default=None,
        description="If set, logs are also written to this file.",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"Log level must be one of {allowed}, got '{v}'")
        return upper


# ---------------------------------------------------------------------------
# Domain-level configs — define agents, tools, workflows
# ---------------------------------------------------------------------------


class ToolParameterSchema(BaseModel, frozen=True):
    """Describes one parameter of a tool's input schema."""

    type: str = Field(description="JSON Schema type (string, integer, boolean…)")
    description: str = Field(description="Human-readable description of the parameter.")
    required: bool = Field(default=True)
    enum: list[str] | None = Field(default=None)


class ToolConfig(BaseModel, frozen=True):
    """
    Configuration for a single callable tool available to an agent.

    Tools are the atomic units of capability. They are defined in YAML
    and registered at runtime — the agent never hardcodes tool logic.
    """

    name: str = Field(description="Unique tool identifier within the domain.")
    description: str = Field(description="What this tool does — shown to the LLM.")
    module: str = Field(
        description="Dotted import path to the tool implementation class."
    )
    parameters: dict[str, ToolParameterSchema] = Field(default_factory=dict)
    enabled: bool = Field(default=True)
    tags: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel, frozen=True):
    """
    Configuration for a single agent within a domain.

    An agent is a LangGraph node. Its behaviour is entirely driven by
    this configuration — prompts, tools, model overrides.
    """

    name: str = Field(description="Unique agent identifier within the domain.")
    description: str = Field(description="Agent's purpose — used in planning.")
    role: str = Field(description="High-level role label (e.g. 'analyst', 'router').")
    system_prompt: str = Field(description="System prompt injected into every call.")
    tools: list[str] = Field(
        default_factory=list,
        description="List of tool names this agent may call.",
    )
    llm_override: LLMConfig | None = Field(
        default=None,
        description="Override the platform LLM config for this agent only.",
    )
    max_iterations: int = Field(default=5, gt=0)
    enabled: bool = Field(default=True)
    tags: list[str] = Field(default_factory=list)


class WorkflowEdge(BaseModel, frozen=True):
    """A directed edge in the LangGraph workflow graph."""

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    condition: str | None = Field(
        default=None,
        description="Optional expression evaluated at runtime to decide traversal.",
    )

    model_config = {"populate_by_name": True}


class WorkflowConfig(BaseModel, frozen=True):
    """
    Configuration for a domain workflow graph.

    Defines the LangGraph state machine: entry point, nodes (agents),
    edges, and the terminal node.
    """

    name: str = Field(description="Workflow identifier.")
    description: str = Field(default="")
    entry_point: str = Field(description="Name of the first node to execute.")
    terminal_node: str = Field(description="Name of the final node.")
    nodes: list[str] = Field(description="Ordered list of node (agent) names.")
    edges: list[WorkflowEdge] = Field(default_factory=list)
    enable_memory: bool = Field(default=True)
    enable_knowledge: bool = Field(default=True)


class EntityFieldConfig(BaseModel, frozen=True):
    """Describes one field of a domain entity schema."""

    type: str = Field(description="Python/JSON type name.")
    description: str = Field(default="")
    required: bool = Field(default=True)
    indexed: bool = Field(default=False)
    searchable: bool = Field(default=False)


class EntityConfig(BaseModel, frozen=True):
    """
    Generic entity schema configuration.

    Allows the platform to understand the structure of domain data
    (e.g. Customer, Employee, Invoice) without hardcoding it.
    """

    name: str = Field(description="Entity class name.")
    table_name: str = Field(description="Underlying database table name.")
    description: str = Field(default="")
    fields: dict[str, EntityFieldConfig] = Field(default_factory=dict)
    primary_key: str = Field(default="id")
    display_name_field: str = Field(
        default="name",
        description="Field used to represent the entity in UI/logs.",
    )


class KnowledgeSourceConfig(BaseModel, frozen=True):
    """Configuration for a knowledge document source."""

    name: str
    type: str = Field(description="Source type: 'file', 'url', 'inline'.")
    path: str | None = Field(default=None)
    content: str | None = Field(default=None)
    chunk_size: int = Field(default=500, gt=0)
    chunk_overlap: int = Field(default=50, ge=0)
    tags: list[str] = Field(default_factory=list)


class DomainConfig(BaseModel, frozen=True):
    """
    Top-level configuration for a business domain.

    A domain is a self-contained unit of business capability.
    Swapping domains is a config change, not a code change.
    """

    name: str = Field(description="Domain identifier (e.g. 'customer_management').")
    display_name: str = Field(description="Human-friendly domain name.")
    description: str = Field(default="")
    version: str = Field(default="1.0.0")
    enabled: bool = Field(default=True)

    entities: list[EntityConfig] = Field(default_factory=list)
    agents: list[AgentConfig] = Field(default_factory=list)
    tools: list[ToolConfig] = Field(default_factory=list)
    workflows: list[WorkflowConfig] = Field(default_factory=list)
    knowledge_sources: list[KnowledgeSourceConfig] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary domain-specific metadata.",
    )


# ---------------------------------------------------------------------------
# Top-level platform config
# ---------------------------------------------------------------------------


class PlatformConfig(BaseModel, frozen=True):
    """
    Root configuration object for the entire platform.

    Loaded once at startup and injected everywhere via the settings module.
    Aggregates infrastructure config and all active domain configs.
    """

    platform_name: str = Field(default="Agentic Decision Intelligence Platform")
    version: str = Field(default="1.0.0")
    environment: str = Field(default="development")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_db: VectorDBConfig = Field(default_factory=VectorDBConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    active_domain: str = Field(
        default="customer_management",
        description="Which domain config is active at runtime.",
    )
    domains: dict[str, DomainConfig] = Field(
        default_factory=dict,
        description="Map of domain name → DomainConfig, all loaded domains.",
    )

    @property
    def current_domain(self) -> DomainConfig:
        """Convenience accessor for the currently active domain."""
        if self.active_domain not in self.domains:
            raise KeyError(
                f"Active domain '{self.active_domain}' not found in loaded domains. "
                f"Available: {list(self.domains.keys())}"
            )
        return self.domains[self.active_domain]
