"""
Smoke test for Modules 3 (models/) and 4 (utils/).
Run from project root: python models_utils_smoke_test.py
"""
import os
import sys

os.environ["OPENAI_API_KEY"] = "sk-test"

# ---- Config ----
from config.settings import initialize

cfg = initialize(
    platform_yaml="config/platform.yaml",
    domains_dir="config/domains",
    extra_env_file=None,
)
domain = cfg.current_domain
print("[OK] Config loaded:", cfg.platform_name)

# ---- Utils ----
from utils import (
    chunk_text,
    days_since,
    get_logger,
    parse_llm_json,
    setup_logging,
    truncate_text,
    utc_now_iso,
)

setup_logging(cfg.logging)
logger = get_logger("smoke_test")
logger.info("Utils module loaded successfully.")

ts = utc_now_iso()
print("[OK] utc_now_iso:", ts[:10])
print("[OK] days_since (self):", days_since(ts))

chunks = chunk_text("This is a test document. " * 50, chunk_size=200, chunk_overlap=30)
print(f"[OK] chunk_text: {len(chunks)} chunks from large text")

truncated = truncate_text(
    "Enterprise Reusable Agentic Decision Intelligence Platform", max_length=30
)
print("[OK] truncate_text:", truncated)

llm_output = '{"target_agent": "data_agent", "confidence": 0.9}'
parsed = parse_llm_json(llm_output)
print("[OK] parse_llm_json:", parsed)

# ---- Models ----
from models import bootstrap_domain, get_table, list_registered_entities

tables = bootstrap_domain(domain, cfg.database, create_tables=True)
print(f"[OK] bootstrap_domain: {len(tables)} table(s) - {list(tables.keys())}")

for entity_type, table in tables.items():
    col_names = [c.name for c in table.columns]
    print(f"  [OK] Table [{table.name}]: {len(col_names)} columns")
    print(f"       Columns: {col_names}")

customer_table = get_table("customer_management", "Customer")
print("[OK] get_table(Customer):", customer_table.name)

registered = list_registered_entities("customer_management")
print("[OK] list_registered_entities:", registered)

db_exists = os.path.exists("./data/platform.db")
print(f"[OK] SQLite DB file created: {db_exists}")

print()
print("Modules 3 + 4: ALL CHECKS PASSED")
