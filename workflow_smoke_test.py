"""
Smoke test for Module 13 (workflow/).

Tests:
    1. GraphBuilder compiles a LangGraph from the YAML workflow config.
    2. WorkflowExecutor bootstraps without error.
    3. Full executor.run() with MOCKED agents (no real LLM calls) — verifies
       that the graph wires correctly and DecisionResult is returned.

Run from project root: python workflow_smoke_test.py
"""
import os, uuid
os.environ["OPENAI_API_KEY"] = "sk-test"

# -----------------------------------------------------------------------
# Bootstrap prerequisite layers
# -----------------------------------------------------------------------
from config.settings import initialize
from utils import setup_logging
cfg = initialize("config/platform.yaml", "config/domains", None)
setup_logging(cfg.logging)
domain = cfg.current_domain
print("[OK] Config loaded:", cfg.platform_name)

from data import bootstrap_data_layer
from memory import get_memory_store
from knowledge import bootstrap_knowledge_layer
from connectors import get_connector
from agents.tool_implementations import register_all_tools
from registry import register_domain_tools, register_domain_agents

bootstrap_data_layer(cfg, seed=True, force_reseed=False)
store = get_memory_store(cfg.vector_db, cfg.embedding)
retrieval_svc = bootstrap_knowledge_layer(cfg, store, force_reingest=False)
connector = get_connector(domain.name)
register_all_tools(connector, retrieval_svc)
tools = register_domain_tools(domain)
agents = register_domain_agents(domain, cfg.llm, tools)
print("[OK] All layers bootstrapped, 6 agents registered")

# -----------------------------------------------------------------------
# Step 1: GraphBuilder — compile without invoking any agent
# -----------------------------------------------------------------------
from workflow.graph_builder import GraphBuilder

workflow_cfg = domain.workflows[0]
builder = GraphBuilder(workflow_cfg, domain.name)
compiled_graph = builder.build()
print(f"\n[OK] LangGraph compiled: workflow='{workflow_cfg.name}'")
print(f"     Nodes: {workflow_cfg.nodes}")
print(f"     Edges: {len(workflow_cfg.edges)} ({sum(1 for e in workflow_cfg.edges if e.condition)} conditional)")

assert compiled_graph is not None

# -----------------------------------------------------------------------
# Step 2: WorkflowExecutor constructor (no run yet)
# -----------------------------------------------------------------------
from workflow.executor import WorkflowExecutor

executor = WorkflowExecutor(domain, cfg, retrieval_svc)
print(f"\n[OK] WorkflowExecutor instantiated for domain='{domain.name}'")

# -----------------------------------------------------------------------
# Step 3: Mock agent invoke() on all registered agents so we get a full
#         graph traversal without real LLM calls.
# -----------------------------------------------------------------------
from registry import get_agent
from schemas.agent import AgentOutput, AgentStatus, WorkflowState
from utils.datetime_utils import utc_now_iso

def make_mock_invoke(agent_name: str, extra_updates: dict = None):
    """Returns a mock invoke() function that writes agent output to state."""
    def _mock_invoke(state: WorkflowState) -> dict:
        output = AgentOutput(
            agent_name=agent_name,
            status=AgentStatus.COMPLETED,
            response=f"[MOCK] {agent_name} processed: {state.get('user_query', '')[:60]}",
            tool_calls_made=[],
            confidence=0.85,
            reasoning=f"{agent_name} mock reasoning.",
        )
        agent_outputs = dict(state.get("agent_outputs", {}))
        agent_outputs[agent_name] = output
        trace = list(state.get("execution_trace", []))
        trace.append({"agent": agent_name, "status": "completed", "timestamp": utc_now_iso()})
        updates = {
            "agent_outputs": agent_outputs,
            "execution_trace": trace,
            "total_tool_calls": state.get("total_tool_calls", 0),
        }
        if extra_updates:
            updates.update(extra_updates)
        return updates
    return _mock_invoke

# Router must set target_agent + intent to trigger conditional routing
def mock_router_invoke(state: WorkflowState) -> dict:
    output = AgentOutput(
        agent_name="router_agent",
        status=AgentStatus.COMPLETED,
        response='{"target_agent": "data_agent", "confidence": 0.93, "intent": "customer_lookup"}',
        tool_calls_made=[],
        confidence=0.93,
    )
    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["router_agent"] = output
    return {
        "agent_outputs": agent_outputs,
        "target_agent": "data_agent",
        "intent": "customer_lookup",
        "routing_confidence": 0.93,
        "routing_reasoning": "User wants customer details.",
        "execution_trace": [{"agent": "router_agent", "status": "completed"}],
        "total_tool_calls": 0,
    }

def mock_synthesizer_invoke(state: WorkflowState) -> dict:
    output = AgentOutput(
        agent_name="synthesizer_agent",
        status=AgentStatus.COMPLETED,
        response="[MOCK FINAL] Customer data retrieved and synthesized. All good.",
        tool_calls_made=[],
        confidence=0.9,
    )
    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["synthesizer_agent"] = output
    return {
        "agent_outputs": agent_outputs,
        "final_response": output.response,
        "workflow_status": "completed",
        "completed_at": utc_now_iso(),
        "execution_trace": list(state.get("execution_trace", [])) + [
            {"agent": "synthesizer_agent", "status": "completed"}
        ],
        "total_tool_calls": state.get("total_tool_calls", 0),
    }

# Patch the compiled graph's nodes with mock functions
# We do this by rebuilding the graph with patched agents
from unittest.mock import patch

# Patch each agent's invoke method in the registry
for agent_name in ["data_agent", "analysis_agent", "decision_agent", "knowledge_agent"]:
    try:
        ag = get_agent(domain.name, agent_name)
        ag.invoke = make_mock_invoke(agent_name)
    except Exception as e:
        print(f"  [WARN] Could not patch {agent_name}: {e}")

router_ag = get_agent(domain.name, "router_agent")
router_ag.invoke = mock_router_invoke

synth_ag = get_agent(domain.name, "synthesizer_agent")
synth_ag.invoke = mock_synthesizer_invoke

# Rebuild the compiled graph with the patched agents
compiled_mock_graph = GraphBuilder(workflow_cfg, domain.name).build()
executor._graph = compiled_mock_graph  # swap in the patched graph
print("\n[OK] Agents patched with mock invoke() functions")
print("     Mock router routes to: data_agent")

# -----------------------------------------------------------------------
# Step 4: Full executor.run() with mocked agents
# -----------------------------------------------------------------------
session_id = f"smoke-test-{uuid.uuid4().hex[:8]}"
query = "What are the details for customer 1?"

print(f"\n[OK] Running executor.run() | query='{query}'")
result = executor.run(query, session_id)

print(f"\n[OK] DecisionResult returned:")
print(f"     result_id:    {result.result_id[:12]}...")
print(f"     domain:       {result.domain}")
print(f"     status:       {result.status}")
print(f"     overall_risk: {result.overall_risk}")
print(f"     recommendations: {len(result.recommendations)}")
print(f"     agents_used:  {result.metadata.get('agents_used', [])}")
print(f"     final_response: {result.metadata.get('final_response', '')[:80]}")

assert result.domain == domain.name
assert len(result.recommendations) > 0
assert "data_agent" in result.metadata.get("agents_used", [])
assert "synthesizer_agent" in result.metadata.get("agents_used", [])

# -----------------------------------------------------------------------
# Step 5: stream() — verify we get intermediate snapshots
# -----------------------------------------------------------------------
print("\n[OK] Testing executor.stream()...")
snapshots = list(executor.stream("Show me customer 2", session_id))
print(f"     Got {len(snapshots)} stream snapshots")
assert len(snapshots) >= 1

print("\nModule 13 (workflow/): ALL CHECKS PASSED")
