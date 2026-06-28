"""
Smoke test for Modules 11 (planner/) and 12 (decision/).
Run from project root: python planner_decision_smoke_test.py
"""
import os
os.environ["OPENAI_API_KEY"] = "sk-test"

from config.settings import initialize
from utils import setup_logging
cfg = initialize("config/platform.yaml", "config/domains", None)
setup_logging(cfg.logging)
print("[OK] Config loaded:", cfg.platform_name)
domain = cfg.current_domain

# --- Bootstrap prerequisite layers ---
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
print("[OK] All prerequisite layers ready")

# -----------------------------------------------------------------------
# Step 1: Planner — initial state
# -----------------------------------------------------------------------
from planner import Planner
from schemas.agent import WorkflowState

planner = Planner(domain)
query = "What is the churn risk for customer 2 and what should we do?"

state = planner.initial_state(query, session_id="smoke-test-session")
print(f"\n[OK] Initial WorkflowState created")
print(f"      run_id: {state['run_id'][:8]}...")
print(f"      domain: {state['domain']}")
print(f"      workflow_status: {state['workflow_status']}")

# -----------------------------------------------------------------------
# Step 2: Planner — pre-routing plan (heuristic mode, no router yet)
# -----------------------------------------------------------------------
plan = planner.plan(query)
print(f"\n[OK] Heuristic plan: intent='{plan.intent.intent}' complexity={plan.estimated_complexity}")
print(f"      Steps ({len(plan.steps)}):")
for s in plan.steps:
    deps = s.depends_on or []
    print(f"        [{s.step_index}] {s.agent_name} (depends_on={deps})")

# -----------------------------------------------------------------------
# Step 3: Simulate router decision and re-plan (post-routing mode)
# -----------------------------------------------------------------------
state["intent"] = "decision_recommendation"
state["target_agent"] = "decision_agent"
state["routing_confidence"] = 0.91
state["routing_reasoning"] = "User wants churn risk analysis AND actionable recommendation."

refined_plan = planner.plan(query, workflow_state=state)
print(f"\n[OK] Refined plan (post-router): intent='{refined_plan.intent.intent}' complexity={refined_plan.estimated_complexity}")
print(f"      Steps ({len(refined_plan.steps)}):")
for s in refined_plan.steps:
    print(f"        [{s.step_index}] {s.agent_name}")

assert len(refined_plan.steps) >= 4, "Expected at least 4 steps for decision_recommendation"
assert any(s.agent_name == "decision_agent" for s in refined_plan.steps)
assert any(s.agent_name == "synthesizer_agent" for s in refined_plan.steps)

# -----------------------------------------------------------------------
# Step 4: Intent parser — entity extraction
# -----------------------------------------------------------------------
from planner.intent_parser import IntentParser
parser = IntentParser(domain)

result = parser.parse("Show me premium customers with high churn risk")
print(f"\n[OK] IntentParser: intent='{result.intent}' target='{result.target_agent}'")
print(f"      entities={result.extracted_entities}")
print(f"      requires_multi_agent={result.requires_multi_agent}")

result2 = parser.parse("What is the policy for handling billing disputes?")
print(f"\n[OK] IntentParser: intent='{result2.intent}' target='{result2.target_agent}'")

# -----------------------------------------------------------------------
# Step 5: Build a realistic WorkflowState with tool results for decision engine
# -----------------------------------------------------------------------
import json
from registry import get_tool
from schemas.agent import AgentOutput, AgentStatus

# Execute real tools to get real data
churn_result = json.loads(get_tool(domain.name, "analyze_churn_risk").invoke({"customer_id": 2}))
detail_result = json.loads(get_tool(domain.name, "get_customer_detail").invoke({"customer_id": 2}))
history_result = json.loads(get_tool(domain.name, "get_interaction_history").invoke({"customer_id": 2, "limit": 5}))
rec_result = json.loads(get_tool(domain.name, "generate_decision_recommendation").invoke(
    {"customer_id": 2, "context": "Two negative billing interactions in 30 days."}
))

state["retrieved_data"] = [
    {"tool": "analyze_churn_risk", "args": {"customer_id": 2}, "result": churn_result},
    {"tool": "get_customer_detail", "args": {"customer_id": 2}, "result": detail_result},
    {"tool": "get_interaction_history", "args": {"customer_id": 2}, "result": history_result},
    {"tool": "generate_decision_recommendation", "args": {"customer_id": 2}, "result": rec_result},
]

# Fake agent outputs
state["agent_outputs"] = {
    "router_agent": AgentOutput(
        agent_name="router_agent",
        status=AgentStatus.COMPLETED,
        response='{"target_agent": "decision_agent", "confidence": 0.91}',
        tool_calls_made=[],
        confidence=0.91,
    ),
    "data_agent": AgentOutput(
        agent_name="data_agent",
        status=AgentStatus.COMPLETED,
        response="Retrieved James Thornton profile and interaction history.",
        tool_calls_made=["get_customer_detail", "get_interaction_history", "analyze_churn_risk"],
        confidence=0.95,
    ),
    "analysis_agent": AgentOutput(
        agent_name="analysis_agent",
        status=AgentStatus.COMPLETED,
        response=(
            "James Thornton presents HIGH churn risk (0.78). "
            "Both recent interactions are NEGATIVE — billing dispute and competitor evaluation. "
            "Sentiment score is -0.45. Recommend urgent retention outreach."
        ),
        tool_calls_made=["analyze_churn_risk"],
        confidence=0.88,
        reasoning="High churn score combined with 100% negative interaction rate signals imminent churn.",
    ),
    "decision_agent": AgentOutput(
        agent_name="decision_agent",
        status=AgentStatus.COMPLETED,
        response=(
            "I recommend immediate retention intervention for James Thornton: "
            "1) Contact within 48 hours with a VP-level call. "
            "2) Resolve billing dispute with immediate credit. "
            "3) Prepare competitive counter-offer given Salesforce evaluation."
        ),
        tool_calls_made=["generate_decision_recommendation"],
        confidence=0.87,
    ),
    "synthesizer_agent": AgentOutput(
        agent_name="synthesizer_agent",
        status=AgentStatus.COMPLETED,
        response=(
            "James Thornton is a Premium customer with HIGH churn risk (0.78). "
            "Two negative interactions around billing have soured the relationship. "
            "Immediate action: VP-level call within 48h, billing credit issued, "
            "competitive retention offer prepared."
        ),
        tool_calls_made=[],
        confidence=0.89,
    ),
}
state["final_response"] = state["agent_outputs"]["synthesizer_agent"].response
state["workflow_status"] = "completed"
state["execution_trace"] = [
    {"agent": "router_agent", "status": "completed", "timestamp": "2026-06-28T14:00:00Z"},
    {"agent": "data_agent", "status": "completed", "timestamp": "2026-06-28T14:00:02Z"},
    {"agent": "analysis_agent", "status": "completed", "timestamp": "2026-06-28T14:00:05Z"},
    {"agent": "decision_agent", "status": "completed", "timestamp": "2026-06-28T14:00:08Z"},
    {"agent": "synthesizer_agent", "status": "completed", "timestamp": "2026-06-28T14:00:10Z"},
]

print(f"\n[OK] WorkflowState populated with real tool results + agent outputs")

# -----------------------------------------------------------------------
# Step 6: DecisionEngine.assemble()
# -----------------------------------------------------------------------
from decision import DecisionEngine, DecisionFormatter

engine = DecisionEngine(domain.name)
decision_result = engine.assemble(state)

# Collect flags and evidence from recommendations
all_flags = [f for r in decision_result.recommendations for f in (r.risk_flags or [])]
all_evidence = [e for r in decision_result.recommendations for e in (r.evidence or [])]
overall_risk_str = (
    decision_result.overall_risk.value
    if hasattr(decision_result.overall_risk, "value")
    else str(decision_result.overall_risk)
)

print(f"\n[OK] DecisionResult assembled:")
print(f"      result_id:          {decision_result.result_id[:12]}...")
print(f"      overall_risk:       {overall_risk_str.upper()}")
print(f"      requires_human:     {decision_result.requires_human_review}")
print(f"      recommendations:    {len(decision_result.recommendations)}")
for r in decision_result.recommendations:
    print(f"        [priority={r.priority}] {r.action[:70]}... (conf={r.confidence_score:.0%})")
print(f"      risk_flags:         {len(all_flags)} (attached to recommendations)")
for f in all_flags:
    level = f.level.value if hasattr(f.level, "value") else f.level
    print(f"        [{level.upper()}] {f.description[:60]}")
print(f"      evidence items:     {len(all_evidence)}")

assert overall_risk_str.lower() in ("high", "critical", "medium")
assert len(decision_result.recommendations) > 0
assert len(all_flags) > 0, "Expected risk flags attached to recommendations"


# -----------------------------------------------------------------------
# Step 7: DecisionFormatter
# -----------------------------------------------------------------------
formatter = DecisionFormatter()
summary = formatter.to_summary_dict(decision_result)
print(f"\n[OK] Summary dict: {len(summary)} keys, risk={summary['overall_risk']}")
assert summary["overall_risk"] == overall_risk_str.upper()

markdown = formatter.to_markdown(decision_result)
print(f"\n[OK] Markdown report: {len(markdown)} chars")
assert "## Decision Intelligence Report" in markdown
assert "Recommendations" in markdown
print("\nFirst 500 chars of markdown:")
print(markdown[:500].encode("ascii", errors="replace").decode("ascii"))

print("\nModules 11 + 12: ALL CHECKS PASSED")
