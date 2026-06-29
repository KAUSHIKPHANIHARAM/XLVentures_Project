import os, json
os.environ['DEMO_MODE'] = '1'
# Ensure project root on path
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import initialize
from connectors import get_connector, register_connector
from agents.tool_implementations import register_all_tools
from registry import tool_registry

cfg = initialize('config/platform.yaml', 'config/domains')
# Ensure connector is registered (bootstrap normally registers it)
conn = register_connector(cfg.current_domain, cfg.database)
register_all_tools(conn, None)

impls = tool_registry._tool_impls

def call(name, *args, **kwargs):
    fn = impls.get(name)
    if not fn:
        return f"NO_IMPL:{name}"
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return f"ERROR calling {name}: {e}"

print('--- search_customers(CUST-002)')
print(call('search_customers', query='CUST-002'))
print('\n--- get_customer_detail(CUST-002)')
print(call('get_customer_detail', 'CUST-002'))
print('\n--- analyze_churn_risk(CUST-002)')
print(call('analyze_churn_risk', 'CUST-002'))
print('\n--- semantic_search_knowledge("billing disputes")')
print(call('semantic_search_knowledge', 'billing disputes'))
print('\n--- get_interaction_history(CUST-003)')
print(call('get_interaction_history', 'CUST-003', limit=5))
print('\n--- generate_decision_recommendation(CUST-002)')
print(call('generate_decision_recommendation', 'CUST-002', context='billing dispute'))
