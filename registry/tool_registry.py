"""
registry/tool_registry.py

ToolRegistry — resolves YAML tool config names to callable tool objects.

The domain YAML lists tools by name and module path. This registry:
    1. Imports the class from the module path (or uses a built-in mapping).
    2. Instantiates it with the ToolConfig parameters.
    3. Caches it for fast lookup by name.

For the hackathon, tools don't need to exist as separate files — they are
created as lightweight callables from their ToolConfig description. The
LangGraph agent uses them via LangChain's StructuredTool interface.

Design:
    - Tools are created lazily on first access.
    - Each tool is domain-scoped (name is unique per domain).
    - The registry returns LangChain-compatible tool objects that LangGraph
      can bind to an agent.
    - Unknown module paths produce a stub tool that logs a warning.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from config.schemas import DomainConfig, ToolConfig
from utils.logging import get_logger

logger = get_logger(__name__)

_tool_cache: dict[tuple[str, str], Any] = {}  # (domain, tool_name) → tool object
_tool_impls: dict[str, Callable[..., Any]] = {}  # tool_name → implementation function
_lock = threading.Lock()


class ToolNotFoundError(Exception):
    """Raised when a tool name cannot be resolved."""


def register_domain_tools(domain_config: DomainConfig) -> dict[str, Any]:
    """
    Register all tools defined in a domain config.

    Creates LangChain StructuredTool objects from each ToolConfig.

    Args:
        domain_config: Domain configuration with tool definitions.

    Returns:
        Dict of tool_name → LangChain Tool object.
    """
    from langchain_core.tools import StructuredTool

    domain = domain_config.name
    registered: dict[str, Any] = {}

    with _lock:
        for tool_config in domain_config.tools:
            if not tool_config.enabled:
                logger.debug("Skipping disabled tool: '%s'.", tool_config.name)
                continue

            key = (domain, tool_config.name)
            if key in _tool_cache:
                registered[tool_config.name] = _tool_cache[key]
                continue

            # Build the LangChain tool — infer schema from function signature
            # so the LLM sees real parameter names/types (not just YAML description).
            impl_fn = _resolve_implementation(tool_config)
            tool_description = (
                impl_fn.__doc__.strip()
                if impl_fn.__doc__
                else tool_config.description.strip()
            )
            lc_tool = StructuredTool.from_function(
                func=impl_fn,
                name=tool_config.name,
                description=tool_description,
                infer_schema=True,
            )
            _tool_cache[key] = lc_tool
            registered[tool_config.name] = lc_tool

            logger.info(
                "Registered tool '%s' for domain '%s'.",
                tool_config.name,
                domain,
            )

    logger.info(
        "Domain '%s': %d tool(s) registered.", domain, len(registered)
    )
    return registered


def get_tool(domain: str, tool_name: str) -> Any:
    """
    Get a registered LangChain Tool by name.

    Args:
        domain:    Domain name.
        tool_name: Tool name as defined in the YAML.

    Returns:
        LangChain StructuredTool.

    Raises:
        ToolNotFoundError: If the tool hasn't been registered.
    """
    key = (domain, tool_name)
    tool = _tool_cache.get(key)
    if tool is None:
        available = [n for (d, n) in _tool_cache if d == domain]
        raise ToolNotFoundError(
            f"Tool '{tool_name}' not found in domain '{domain}'. "
            f"Available: {available}"
        )
    return tool


def get_tools_for_agent(
    domain: str, tool_names: list[str]
) -> list[Any]:
    """
    Get multiple registered tools by name (for binding to an agent).

    Args:
        domain:     Domain name.
        tool_names: List of tool names the agent is configured to use.

    Returns:
        List of LangChain Tool objects.
    """
    tools = []
    for name in tool_names:
        try:
            tools.append(get_tool(domain, name))
        except ToolNotFoundError:
            logger.warning(
                "Agent requested tool '%s' but it's not registered. Skipping.",
                name,
            )
    return tools


def register_tool_implementation(
    tool_name: str, func: Callable[..., Any]
) -> None:
    """
    Register a concrete implementation function for a tool.

    This allows modules to provide real implementations that the
    registry maps to tool names. Called by connector, decision, and
    knowledge modules during bootstrap.

    Args:
        tool_name: Tool name matching the YAML config.
        func:      The callable implementation.
    """
    _tool_impls[tool_name] = func
    logger.debug("Tool implementation registered: '%s'.", tool_name)


def reset_tool_registry() -> None:
    """Clear all cached tools (for tests only)."""
    global _tool_cache, _tool_impls  # noqa: PLW0603
    with _lock:
        _tool_cache = {}
        _tool_impls = {}
    logger.debug("Tool registry reset.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_implementation(tool_config: ToolConfig) -> Callable[..., Any]:
    """
    Resolve the implementation function for a tool.

    Priority:
        1. Explicitly registered implementation (via register_tool_implementation).
        2. Stub function that returns a descriptive placeholder.
    """
    # Check explicitly registered implementations
    if tool_config.name in _tool_impls:
        logger.debug(
            "Tool '%s' resolved to registered implementation.",
            tool_config.name,
        )
        return _tool_impls[tool_config.name]

    # Return a stub — the tool is defined but no implementation exists yet.
    # This allows the platform to start and agents to see the tool schema
    # even before the concrete module is built.
    logger.info(
        "Tool '%s' has no registered implementation. "
        "Using descriptive stub. Module: '%s'.",
        tool_config.name,
        tool_config.module,
    )
    return _make_stub(tool_config)


def _make_stub(tool_config: ToolConfig) -> Callable[..., str]:
    """Create a stub function that describes what the tool would do."""
    def stub(**kwargs: Any) -> str:
        return (
            f"[Tool '{tool_config.name}' executed with args: {kwargs}] "
            f"Description: {tool_config.description.strip()}"
        )

    stub.__name__ = tool_config.name
    stub.__doc__ = tool_config.description.strip()
    return stub
