"""
registry/__init__.py

Public API for the registry module.

Usage:
    from registry import register_domain_tools, get_tool, get_tools_for_agent
    from registry import register_domain_agents, get_agent
    from registry import register_tool_implementation
"""

from registry.agent_registry import (
    AgentNotFoundError,
    get_agent,
    register_domain_agents,
    reset_agent_registry,
)
from registry.tool_registry import (
    ToolNotFoundError,
    get_tool,
    get_tools_for_agent,
    register_domain_tools,
    register_tool_implementation,
    reset_tool_registry,
)

__all__ = [
    # Tools
    "register_domain_tools",
    "get_tool",
    "get_tools_for_agent",
    "register_tool_implementation",
    "reset_tool_registry",
    "ToolNotFoundError",
    # Agents
    "register_domain_agents",
    "get_agent",
    "reset_agent_registry",
    "AgentNotFoundError",
]
