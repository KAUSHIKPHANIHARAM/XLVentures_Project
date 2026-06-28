"""
Smoke test for Modules 5 (connectors/) and 6 (data/).
Run from project root: python connectors_data_smoke_test.py
"""
import os
os.environ["OPENAI_API_KEY"] = "sk-test"

# Remove old DB so we test fresh seeding
import pathlib
db_path = pathlib.Path("./data/platform.db")
if db_path.exists():
    db_path.unlink()
    print("[OK] Cleared old DB for fresh test")

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

# Step 2: Full data layer bootstrap (creates tables + seeds data)
from data import bootstrap_data_layer
bootstrap_data_layer(cfg, seed=True, force_reseed=False)
print("[OK] Data layer bootstrapped and seeded")

# Step 3: Get connector
from connectors import get_connector
conn = get_connector("customer_management")
print("[OK] Connector retrieved:", type(conn).__name__)

# Step 4: Health check
assert conn.health_check(), "Health check failed!"
print("[OK] Health check: PASS")

# Step 5: get_all
result = conn.get_all("Customer", limit=10)
print(f"[OK] get_all(Customer): {result.total_found} records found")
for r in result.records:
    print(f"      - [{r.entity_id}] {r.display_name} | segment={r.get_field('segment')} | churn={r.get_field('churn_risk_score')}")

# Step 6: get_by_id
customer = conn.get_by_id("Customer", 1)
assert customer is not None, "Customer 1 not found!"
print(f"\n[OK] get_by_id(1): {customer.display_name} | LTV=${customer.get_field('lifetime_value')}")

# Step 7: search (text)
search_result = conn.search("Customer", query="Premium")
print(f"\n[OK] search('Premium'): found {search_result.total_found} records")

# Step 8: filter_by (churn risk)
high_risk = conn.filter_by("Customer", filters={"segment": "Premium"}, order_by="churn_risk_score", descending=True)
print(f"\n[OK] filter_by(segment=Premium): {high_risk.total_found} records")
for r in high_risk.records:
    print(f"      - {r.display_name} | churn={r.get_field('churn_risk_score')}")

# Step 9: get all Interactions
interactions = conn.get_all("Interaction", limit=5)
print(f"\n[OK] get_all(Interaction): {interactions.total_found} records (showing 5)")
for r in interactions.records:
    print(f"      - [{r.entity_id}] cust_id={r.get_field('customer_id')} | {r.display_name[:50]}")

# Step 10: filter interactions for customer 2 (the high churn risk one)
cust2_interactions = conn.filter_by("Interaction", filters={"customer_id": 2})
print(f"\n[OK] Interactions for customer 2: {cust2_interactions.total_found} found")
for r in cust2_interactions.records:
    print(f"      - [{r.get_field('sentiment').upper()}] {r.display_name}")

print("\nModules 5 + 6: ALL CHECKS PASSED")
