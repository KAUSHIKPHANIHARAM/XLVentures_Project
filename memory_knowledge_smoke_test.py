"""
Smoke test for Modules 7 (memory/) and 8 (knowledge/).
Run from project root: python memory_knowledge_smoke_test.py
"""
import os
os.environ["OPENAI_API_KEY"] = "sk-test"  # triggers local embedding fallback

# Step 1: Config
from config.settings import initialize
cfg = initialize(
    platform_yaml="config/platform.yaml",
    domains_dir="config/domains",
    extra_env_file=None,
)
from utils import setup_logging
setup_logging(cfg.logging)
print("[OK] Config loaded:", cfg.platform_name)

# Step 2: Init memory store
from memory import get_memory_store, EpisodicMemory
store = get_memory_store(cfg.vector_db, cfg.embedding)
print("[OK] Memory store initialized:", type(store).__name__)

# Step 3: Health check
assert store.health_check(), "Memory store health check failed!"
print("[OK] Memory store health check: PASS")

# Step 4: Bootstrap knowledge layer (ingests domain YAML knowledge sources)
from knowledge import bootstrap_knowledge_layer, get_retrieval_service
retriever = bootstrap_knowledge_layer(cfg, store, force_reingest=True)
print("[OK] Knowledge layer bootstrapped")

# Step 5: Verify chunks stored
count = retriever.knowledge_count()
print(f"[OK] Knowledge chunks stored: {count}")
assert count > 0, "No knowledge chunks were stored!"

# Step 6: Semantic retrieval
result = retriever.retrieve("What should I do with a high churn risk customer?", top_k=3)
print(f"\n[OK] Semantic retrieval: {result.total_found} chunk(s) retrieved")
for r in result.results:
    source = r.metadata.get("meta_source_name", "unknown")
    print(f"  similarity={r.similarity_score:.3f} | source={source}")
    print(f"  content: {r.content[:100].strip()}...")

# Step 7: retrieve_as_context (formatted for agent prompt injection)
context = retriever.retrieve_as_context(
    "escalation policy for angry premium customer", top_k=2, min_similarity=0.1
)
print(f"\n[OK] Context block generated ({len(context)} chars)")
print(context[:300] + "..." if len(context) > 300 else context)

# Step 8: Episodic memory — record a fake agent output
from schemas.agent import AgentOutput, AgentStatus
from schemas.memory import MemoryType

episodic = EpisodicMemory(store=store, domain=cfg.active_domain)

fake_output = AgentOutput(
    agent_name="analysis_agent",
    status=AgentStatus.COMPLETED,
    response="Customer James Thornton has churn risk 0.78 — HIGH. Two negative interactions in 30 days.",
    tool_calls_made=["get_customer_detail", "analyze_churn_risk"],
    confidence=0.88,
)

entry_id = episodic.record(
    session_id="sess-test-001",
    agent_output=fake_output,
    user_query="What is the churn risk for James Thornton?",
    entity_id="2",
    entity_type="Customer",
)
print(f"\n[OK] Episodic memory recorded: entry_id={entry_id[:12]}...")
print(f"[OK] Total episodic entries: {episodic.entry_count()}")

# Step 9: Episodic retrieval
ep_result = episodic.retrieve_relevant(
    query="James Thornton churn risk",
    top_k=3,
    entity_id="2",
)
print(f"\n[OK] Episodic retrieval for customer 2: {ep_result.total_found} result(s)")
if ep_result.results:
    top = ep_result.results[0]
    print(f"  Top result similarity={top.similarity_score:.3f}")
    print(f"  Content: {top.content[:120]}...")

# Step 10: Verify collections exist
episodic_count = store.count(cfg.active_domain, MemoryType.EPISODIC)
semantic_count = store.count(cfg.active_domain, MemoryType.SEMANTIC)
print(f"\n[OK] ChromaDB collections:")
print(f"  Episodic: {episodic_count} entries")
print(f"  Semantic: {semantic_count} entries")

print("\nModules 7 + 8: ALL CHECKS PASSED")
