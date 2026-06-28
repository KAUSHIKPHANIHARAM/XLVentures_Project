"""
workflow/executor.py

WorkflowExecutor — top-level orchestration facade.

Single public method: run(query, session_id) → DecisionResult

Internal sequence:
    1. Planner creates initial WorkflowState (no LLM cost).
    2. Knowledge retrieval pre-populates state["knowledge_chunks"] from ChromaDB.
    3. GraphBuilder builds the compiled LangGraph graph for the domain.
    4. Graph.invoke() runs: RouterAgent → specialist chain → SynthesizerAgent.
    5. DecisionEngine assembles a typed DecisionResult from the final state.

Config-driven:
    - Which workflow graph to use comes from the YAML (first workflow in domain).
    - Agents and tools are looked up from registries.
    - Nothing is hardcoded.
"""

from __future__ import annotations

from typing import Any

from config.schemas import PlatformConfig, DomainConfig
from decision.engine import DecisionEngine
from knowledge.retrieval import KnowledgeRetrievalService
from planner.planner import Planner
from schemas.agent import WorkflowState
from schemas.decision import DecisionResult
from utils.datetime_utils import utc_now_iso
from utils.logging import get_logger
from workflow.graph_builder import GraphBuilder

logger = get_logger(__name__)

_KNOWLEDGE_TOP_K = 5


class WorkflowExecutor:
    """
    Orchestrates a full end-to-end agentic workflow run.

    Lifecycle:
        Instantiate once per domain (the compiled graph is cached on `self`).
        Call run() for each user query.

    Args:
        domain_config:     Domain configuration (agents, tools, workflows).
        app_config:        Platform-level config (LLM settings, etc.).
        retrieval_service: Knowledge retrieval for pre-populating chunks.
    """

    def __init__(
        self,
        domain_config: DomainConfig,
        app_config: PlatformConfig,
        retrieval_service: KnowledgeRetrievalService | None = None,
    ) -> None:
        self._domain = domain_config.name
        self._domain_config = domain_config
        self._app_config = app_config
        self._retrieval_service = retrieval_service

        # Build components
        self._planner = Planner(domain_config)
        self._decision_engine = DecisionEngine(domain_config.name)

        # Build and compile graph (expensive; done once at construction)
        workflow = self._get_primary_workflow()
        self._graph = GraphBuilder(workflow, domain_config.name).build()
        logger.info(
            "WorkflowExecutor ready for domain '%s' (workflow='%s')",
            domain_config.name, workflow.name,
        )

    def run(self, query: str, session_id: str) -> DecisionResult:
        """
        Execute a full agentic workflow for a user query.

        Args:
            query:      Natural language question or instruction.
            session_id: Unique session identifier for memory/audit.

        Returns:
            A structured, explainable DecisionResult.
        """
        logger.info(
            "WorkflowExecutor.run() | session='%s' | query='%.80s'",
            session_id, query,
        )

        # Step 1: Create initial state
        state: WorkflowState = self._planner.initial_state(query, session_id)

        # Step 2: Pre-populate knowledge chunks (zero-LLM retrieval)
        state = self._prefetch_knowledge(state, query)

        # Step 3: Run the compiled LangGraph graph
        logger.info("Invoking LangGraph for domain '%s'...", self._domain)
        try:
            final_state: WorkflowState = self._graph.invoke(
                state,
                config={"recursion_limit": 25},
            )
        except Exception as exc:
            logger.error("LangGraph execution failed: %s", exc, exc_info=True)
            final_state = dict(state)  # type: ignore[assignment]
            final_state["workflow_status"] = "failed"
            final_state["error"] = str(exc)
            final_state["final_response"] = (
                f"Workflow execution encountered an error: {exc}"
            )
            final_state["completed_at"] = utc_now_iso()

        logger.info(
            "Graph completed | status='%s' | agents=%s",
            final_state.get("workflow_status"),
            list(final_state.get("agent_outputs", {}).keys()),
        )

        # Step 4: Assemble DecisionResult
        result = self._decision_engine.assemble(final_state)
        return result

    def stream(self, query: str, session_id: str):
        """
        Stream workflow execution step-by-step (yields state snapshots).

        Yields:
            dict — intermediate WorkflowState after each agent completes.
        """
        state: WorkflowState = self._planner.initial_state(query, session_id)
        state = self._prefetch_knowledge(state, query)

        for snapshot in self._graph.stream(
            state,
            config={"recursion_limit": 25},
        ):
            yield snapshot

    def _prefetch_knowledge(
        self, state: WorkflowState, query: str
    ) -> WorkflowState:
        """
        Retrieve relevant knowledge chunks from ChromaDB before graph starts.

        Adds knowledge_chunks to state so agents can reference them without
        needing to call the semantic_search tool themselves.
        """
        if not self._retrieval_service:
            return state

        try:
            retrieval_result = self._retrieval_service.retrieve(
                query=query,
                top_k=_KNOWLEDGE_TOP_K,
            )
            chunks = retrieval_result.results if retrieval_result else []
            if chunks:
                # Convert RetrievedMemory → dict for state transport
                state = dict(state)  # type: ignore[assignment]
                state["knowledge_chunks"] = [
                    {
                        "content": chunk.content,
                        "source": chunk.metadata.get("source_name", "knowledge_base"),
                        "similarity": chunk.similarity_score,
                        "tags": chunk.tags,
                    }
                    for chunk in chunks
                ]
                logger.info(
                    "Pre-fetched %d knowledge chunks for query: '%.50s'",
                    len(chunks), query,
                )
        except Exception as exc:
            logger.warning("Knowledge pre-fetch failed (non-fatal): %s", exc)

        return state

    def _get_primary_workflow(self):
        """Return the first workflow from the domain config."""
        if not self._domain_config.workflows:
            raise ValueError(
                f"Domain '{self._domain}' has no workflow definitions in YAML."
            )
        return self._domain_config.workflows[0]
