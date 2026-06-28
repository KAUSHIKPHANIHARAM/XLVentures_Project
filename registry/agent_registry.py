"""
registry/agent_registry.py

AgentRegistry — maps YAML AgentConfig names to instantiated BaseAgent objects.

At startup, the platform reads AgentConfig objects from the domain YAML,
resolves each to the correct BaseAgent subclass based on the agent's role,
injects tools and configuration, and caches the result.

Design:
    - Role-to-class mapping: 'router' → RouterAgent, 'analyst' → AnalysisAgent, etc.
    - Tools are injected from the ToolRegistry (already resolved LangChain Tools).
    - One registry per domain — agents are domain-scoped.
    - LLMConfig override: if an agent defines llm_override, it gets its own LLM.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from config.schemas import AgentConfig, DomainConfig, LLMConfig
from utils.logging import get_logger

if TYPE_CHECKING:
    from agents.base import BaseAgent

logger = get_logger(__name__)

_agent_cache: dict[tuple[str, str], "BaseAgent"] = {}  # (domain, agent_name) → agent
_lock = threading.Lock()


class AgentNotFoundError(Exception):
    """Raised when an agent name cannot be resolved."""


def register_domain_agents(
    domain_config: DomainConfig,
    platform_llm_config: LLMConfig,
    registered_tools: dict[str, Any],
) -> dict[str, "BaseAgent"]:
    """
    Instantiate and register all agents for a domain.

    Args:
        domain_config:      Domain configuration with agent definitions.
        platform_llm_config: Default LLM config (overridable per-agent).
        registered_tools:   Dict of tool_name → LangChain Tool (from ToolRegistry).

    Returns:
        Dict of agent_name → BaseAgent instance.
    """
    domain = domain_config.name
    registered: dict[str, "BaseAgent"] = {}

    with _lock:
        for agent_config in domain_config.agents:
            if not agent_config.enabled:
                logger.debug("Skipping disabled agent: '%s'.", agent_config.name)
                continue

            key = (domain, agent_config.name)
            if key in _agent_cache:
                registered[agent_config.name] = _agent_cache[key]
                continue

            # Resolve which tools this agent gets
            agent_tools = [
                registered_tools[t]
                for t in agent_config.tools
                if t in registered_tools
            ]

            # Build effective LLM config (agent override or platform default)
            effective_llm = agent_config.llm_override or platform_llm_config

            # Instantiate the correct BaseAgent subclass by role
            agent = _create_agent(
                agent_config=agent_config,
                llm_config=effective_llm,
                tools=agent_tools,
                domain=domain,
            )

            _agent_cache[key] = agent
            registered[agent_config.name] = agent
            logger.info(
                "Registered agent '%s' (role=%s) for domain '%s' with %d tool(s).",
                agent_config.name,
                agent_config.role,
                domain,
                len(agent_tools),
            )

    logger.info(
        "Domain '%s': %d agent(s) registered.", domain, len(registered)
    )
    return registered


def get_agent(domain: str, agent_name: str) -> "BaseAgent":
    """
    Retrieve a registered agent by name.

    Args:
        domain:     Domain name.
        agent_name: Agent name as defined in the YAML.

    Returns:
        BaseAgent instance.

    Raises:
        AgentNotFoundError: If not registered.
    """
    key = (domain, agent_name)
    agent = _agent_cache.get(key)
    if agent is None:
        available = [n for (d, n) in _agent_cache if d == domain]
        raise AgentNotFoundError(
            f"Agent '{agent_name}' not found in domain '{domain}'. "
            f"Available: {available}"
        )
    return agent


def reset_agent_registry() -> None:
    """Clear all cached agents (for tests only)."""
    global _agent_cache  # noqa: PLW0603
    with _lock:
        _agent_cache = {}
    logger.debug("Agent registry reset.")


# ---------------------------------------------------------------------------
# Private factory
# ---------------------------------------------------------------------------

_ROLE_TO_CLASS: dict[str, str] = {
    "router": "agents.implementations.router.RouterAgent",
    "data_retrieval": "agents.implementations.data.DataAgent",
    "analyst": "agents.implementations.analysis.AnalysisAgent",
    "decision_maker": "agents.implementations.decision.DecisionAgent",
    "knowledge_retrieval": "agents.implementations.knowledge.KnowledgeAgent",
    "synthesizer": "agents.implementations.synthesizer.SynthesizerAgent",
}


def _create_agent(
    agent_config: AgentConfig,
    llm_config: LLMConfig,
    tools: list[Any],
    domain: str,
) -> "BaseAgent":
    """Dynamically import and instantiate the correct BaseAgent subclass."""
    role = agent_config.role
    class_path = _ROLE_TO_CLASS.get(role)

    if class_path is None:
        logger.warning(
            "No agent class mapped for role '%s'. Falling back to BaseToolAgent.", role
        )
        class_path = "agents.implementations.data.DataAgent"

    module_path, class_name = class_path.rsplit(".", 1)

    try:
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls(
            config=agent_config,
            llm_config=llm_config,
            tools=tools,
            domain=domain,
        )
    except (ImportError, AttributeError) as exc:
        raise AgentNotFoundError(
            f"Could not instantiate agent class '{class_path}': {exc}"
        ) from exc
