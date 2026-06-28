"""
Smoke test for config/ module.
Run from project root: python -m config._smoke_test
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set a dummy API key so env resolution works
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-smoke-test")

from config.settings import initialize, get_config

def main():
    print("=" * 60)
    print("CONFIG MODULE SMOKE TEST")
    print("=" * 60)

    cfg = initialize(
        platform_yaml="config/platform.yaml",
        domains_dir="config/domains",
        extra_env_file=None,  # no .env in test
    )

    print(f"\n[OK] Platform     : {cfg.platform_name}")
    print(f"[OK] Version      : {cfg.version}")
    print(f"[OK] Environment  : {cfg.environment}")
    print(f"[OK] Active Domain: {cfg.active_domain}")
    print(f"[OK] LLM Model    : {cfg.llm.model}")
    print(f"[OK] Embedding    : {cfg.embedding.model}")
    print(f"[OK] Vector DB    : {cfg.vector_db.provider} -> {cfg.vector_db.persist_directory}")
    print(f"[OK] Database     : {cfg.database.provider} -> {cfg.database.connection_string}")
    print(f"[OK] Log Level    : {cfg.logging.level}")
    print(f"\n[OK] Loaded {len(cfg.domains)} domain(s): {list(cfg.domains.keys())}")

    domain = cfg.current_domain
    print(f"\n--- Active Domain: {domain.display_name} ---")
    print(f"[OK] Entities     : {[e.name for e in domain.entities]}")
    print(f"[OK] Tools        : {[t.name for t in domain.tools]}")
    print(f"[OK] Agents       : {[a.name for a in domain.agents]}")
    print(f"[OK] Workflows    : {[w.name for w in domain.workflows]}")
    print(f"[OK] Knowledge    : {[k.name for k in domain.knowledge_sources]}")

    workflow = domain.workflows[0]
    print(f"\n--- Workflow: {workflow.name} ---")
    print(f"[OK] Entry Point  : {workflow.entry_point}")
    print(f"[OK] Terminal     : {workflow.terminal_node}")
    print(f"[OK] Nodes        : {workflow.nodes}")
    print(f"[OK] Edges        : {len(workflow.edges)} defined")

    router = next(a for a in domain.agents if a.name == "router_agent")
    print(f"\n--- Agent: {router.name} ({router.role}) ---")
    print(f"[OK] Tools        : {router.tools}")
    print(f"[OK] Prompt       : {router.system_prompt[:60].strip()}...")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED — config/ module is working correctly.")
    print("=" * 60)

if __name__ == "__main__":
    main()
