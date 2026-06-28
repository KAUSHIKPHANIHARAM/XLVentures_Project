"""
Smoke test for Modules 9 (registry/) and 10 (agents/).

This test does NOT call the OpenAI API — it verifies that:
    1. Tools are registered and callable (returning stub or real output).
    2. Agents can be instantiated from YAML config.
    3. BaseAgent's invoke() works end-to-end with a mock LLM.

Run from project root: python registry_agents_smoke_test.py
"""
import os
os.environ["OPENAI_API_KEY"] = "sk-test"

from config.settings import initialize
from utils import setup_logging

cfg = initialize("config/platform.yaml", "config/domains", None)
setup_logging(cfg.logging)
print("[OK] Config loaded:", cfg.platform_name)
domain = cfg.current_domain

# -----------------------------------------------------------------------
# Step 1: Bootstrap data + memory layers (prereqs for tool impls)
# -----------------------------------------------------------------------
from data import bootstrap_data_layer
from memory import get_memory_store
from knowledge import bootstrap_knowledge_layer
from connectors import get_connector

bootstrap_data_layer(cfg, seed=True, force_reseed=False)
store = get_memory_store(cfg.vector_db, cfg.embedding)
retrieval_svc = bootstrap_knowledge_layer(cfg, store, force_reingest=False)
connector = get_connector(domain.name)
print("[OK] Data + Memory + Knowledge layers ready")

# -----------------------------------------------------------------------
# Step 2: Register tool implementations
# -----------------------------------------------------------------------
from agents.tool_implementations import register_all_tools
register_all_tools(connector, retrieval_svc)
print("[OK] Tool implementations registered")

# -----------------------------------------------------------------------
# Step 3: Register tools with the ToolRegistry
# -----------------------------------------------------------------------
from registry import register_domain_tools
tools = register_domain_tools(domain)
print(f"[OK] LangChain tools created: {list(tools.keys())}")
assert len(tools) > 0, "No tools registered!"

# -----------------------------------------------------------------------
# Step 4: Verify tool execution (no LLM needed)
# -----------------------------------------------------------------------
import json
from registry import get_tool

# Test search_customers
search_tool = get_tool(domain.name, "search_customers")
result = search_tool.invoke({"query": "James", "segment": "", "limit": 3})
result_dict = json.loads(result)
print(f"\n[OK] search_customers('James'): {result_dict['total_found']} found")
for c in result_dict["customers"]:
    print(f"      - {c['name']} | churn={c['churn_risk_score']}")

# Test get_customer_detail
detail_tool = get_tool(domain.name, "get_customer_detail")
detail = json.loads(detail_tool.invoke({"customer_id": 2}))
print(f"\n[OK] get_customer_detail(2): {detail['display_name']}")

# Test analyze_churn_risk
churn_tool = get_tool(domain.name, "analyze_churn_risk")
churn = json.loads(churn_tool.invoke({"customer_id": 2}))
print(f"\n[OK] analyze_churn_risk(2): {churn['risk_label']} ({churn['churn_risk_score']})")
print(f"      {churn['analysis']}")

# Test semantic_search_knowledge
knowledge_tool = get_tool(domain.name, "semantic_search_knowledge")
kb_result = json.loads(knowledge_tool.invoke({"query": "churn prevention policy", "top_k": 2}))
print(f"\n[OK] semantic_search_knowledge: {kb_result['chunks_found']} chunk(s)")

# -----------------------------------------------------------------------
# Step 5: Register agents
# -----------------------------------------------------------------------
from registry import register_domain_agents
agents = register_domain_agents(domain, cfg.llm, tools)
print(f"\n[OK] Agents registered: {list(agents.keys())}")
assert "router_agent" in agents, "router_agent not registered!"
assert "data_agent" in agents, "data_agent not registered!"
assert "synthesizer_agent" in agents, "synthesizer_agent not registered!"

# -----------------------------------------------------------------------
# Step 6: Verify agent instantiation and WorkflowState structure
# -----------------------------------------------------------------------
from registry import get_agent
from schemas.agent import WorkflowState

router = get_agent(domain.name, "router_agent")
data_agent = get_agent(domain.name, "data_agent")
synth = get_agent(domain.name, "synthesizer_agent")

print(f"\n[OK] RouterAgent: name={router.name}, role={router.role}, tools={len(router.tools)}")
print(f"[OK] DataAgent:   name={data_agent.name}, role={data_agent.role}, tools={len(data_agent.tools)}")
print(f"[OK] Synthesizer: name={synth.name}, role={synth.role}, tools={len(synth.tools)}")

# -----------------------------------------------------------------------
# Step 7: Dry-run agent invoke with mock LLM (no API call)
# -----------------------------------------------------------------------
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage

# Create a minimal WorkflowState
state: WorkflowState = {
    "user_query": "What is the churn risk for James Thornton?",
    "session_id": "test-session-001",
    "domain": domain.name,
    "intent": "",
    "target_agent": "",
    "routing_confidence": 0.0,
    "routing_reasoning": "",
    "agent_outputs": {},
    "retrieved_data": [],
    "knowledge_chunks": [],
    "final_response": "",
    "workflow_status": "running",
    "execution_trace": [],
    "entity_context": {},
    "completed_at": "",
}

# Mock the LLM to return a routing JSON without hitting the API
mock_router_response = AIMessage(
    content='{"target_agent": "data_agent", "intent": "churn risk analysis for James Thornton", "confidence": 0.92, "reasoning": "User is asking for churn analysis on a named customer."}'
)

with patch.object(router, "_call_llm", return_value=mock_router_response):
    updates = router.invoke(state)

print(f"\n[OK] RouterAgent.invoke() succeeded")
print(f"      target_agent = {updates.get('target_agent')}")
print(f"      intent       = {updates.get('intent')}")
print(f"      confidence   = {updates.get('routing_confidence')}")
assert updates.get("target_agent") == "data_agent"
assert "router_agent" in updates["agent_outputs"]

# Apply state updates
state.update(updates)

# Mock data_agent to simulate tool calls
mock_data_response = AIMessage(content="Retrieved customer data for James Thornton.")
with patch.object(data_agent, "_call_llm", return_value=mock_data_response):
    data_updates = data_agent.invoke(state)

print(f"\n[OK] DataAgent.invoke() succeeded")
assert "data_agent" in data_updates["agent_outputs"]
state.update(data_updates)

print(f"\n[OK] Execution trace has {len(state['execution_trace'])} step(s)")
for step in state["execution_trace"]:
    print(f"      [{step['status'].upper()}] {step['agent']}")

print("\nModules 9 + 10: ALL CHECKS PASSED")
