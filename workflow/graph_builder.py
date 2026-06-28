"""
workflow/graph_builder.py

GraphBuilder — converts WorkflowConfig YAML into a LangGraph StateGraph.

Reads the domain YAML's workflow definition (nodes, edges, entry_point,
terminal_node) and builds a compiled LangGraph graph. Each node maps to a
registered BaseAgent's invoke() method. Conditional edges are driven by
state["target_agent"] (set by RouterAgent).

Design:
    - Fully config-driven: zero hardcoded agent names or routing logic.
    - Conditional edges: any YAML edge with a non-null condition is treated
      as a conditional branch from the router node.
    - Unconditional edges: YAML edges with condition=None are straight edges.
    - The terminal node always connects to END.
    - Returns a compiled LangGraph graph ready for .invoke() or .stream().
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from config.schemas import WorkflowConfig
from registry.agent_registry import AgentNotFoundError, get_agent
from schemas.agent import WorkflowState
from utils.logging import get_logger

logger = get_logger(__name__)


class GraphBuilder:
    """
    Builds a compiled LangGraph StateGraph from a WorkflowConfig.

    Args:
        workflow_config: The WorkflowConfig parsed from the domain YAML.
        domain:          Domain name (for agent registry lookup).
    """

    def __init__(self, workflow_config: WorkflowConfig, domain: str) -> None:
        self._config = workflow_config
        self._domain = domain

    def build(self) -> Any:
        """
        Build and compile the LangGraph StateGraph.

        Returns:
            A compiled LangGraph graph (supports .invoke() and .stream()).
        """
        graph = StateGraph(WorkflowState)

        # --- Add nodes ---
        for node_name in self._config.nodes:
            try:
                agent = get_agent(self._domain, node_name)
                graph.add_node(node_name, agent.invoke)
                logger.debug("Graph node added: '%s'", node_name)
            except AgentNotFoundError:
                logger.warning(
                    "Agent '%s' not found in registry — skipping node.", node_name
                )

        # --- Separate conditional from unconditional edges ---
        conditional_sources: dict[str, list[tuple[str, str]]] = {}
        unconditional_edges: list[tuple[str, str]] = []

        for edge in self._config.edges:
            if edge.condition:
                # Collect all conditional branches from the same source node
                if edge.from_node not in conditional_sources:
                    conditional_sources[edge.from_node] = []
                conditional_sources[edge.from_node].append(
                    (edge.to_node, edge.condition)
                )
            else:
                unconditional_edges.append((edge.from_node, edge.to_node))

        # --- Add conditional edges (from router to specialists) ---
        for source_node, branches in conditional_sources.items():
            # Build the mapping: {target_agent_value → node_name}
            routing_map: dict[str, str] = {}
            for to_node, _condition in branches:
                routing_map[to_node] = to_node

            def _make_router(rmap: dict[str, str]) -> Any:
                """Create a routing function closed over the routing map."""
                def _route(state: WorkflowState) -> str:
                    target = state.get("target_agent", "")
                    if target in rmap:
                        logger.debug("Routing to: '%s'", target)
                        return rmap[target]
                    # Fallback: use first available node
                    fallback = next(iter(rmap))
                    logger.warning(
                        "target_agent='%s' not in routing map %s. "
                        "Falling back to '%s'.",
                        target, list(rmap.keys()), fallback,
                    )
                    return fallback
                return _route

            graph.add_conditional_edges(
                source_node,
                _make_router(routing_map),
                routing_map,
            )
            logger.debug(
                "Conditional edges from '%s' → %s", source_node, list(routing_map.keys())
            )

        # --- Add unconditional edges ---
        terminal = self._config.terminal_node
        for from_node, to_node in unconditional_edges:
            if to_node == terminal:
                graph.add_edge(from_node, to_node)
            else:
                graph.add_edge(from_node, to_node)
            logger.debug("Unconditional edge: '%s' → '%s'", from_node, to_node)

        # --- Terminal node → END ---
        graph.add_edge(terminal, END)
        logger.debug("Terminal edge: '%s' → END", terminal)

        # --- Set entry point ---
        graph.set_entry_point(self._config.entry_point)
        logger.debug("Entry point: '%s'", self._config.entry_point)

        # --- Compile ---
        compiled = graph.compile()
        logger.info(
            "LangGraph compiled. Workflow='%s' nodes=%d edges=%d",
            self._config.name,
            len(self._config.nodes),
            len(self._config.edges),
        )
        return compiled
