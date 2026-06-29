"""
Inspect domain YAML entity schemas vs SQLite database tables.
Prints expected columns and actual columns and any differences.
"""
import json
import sqlite3
from pathlib import Path
import sys

# Ensure project root is on sys.path for local imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import initialize

cfg = initialize(platform_yaml='config/platform.yaml', domains_dir='config/domains')
domain = cfg.current_domain

db_path = cfg.database.connection_string
if cfg.database.provider == 'sqlite' and not db_path.startswith('sqlite'):
    # path may be './data/platform.db'
    sqlite_path = Path(db_path)
else:
    sqlite_path = Path(db_path.replace('sqlite:///', ''))

print(json.dumps({'db_exists': sqlite_path.exists(), 'db_path': str(sqlite_path)}))

expected = {}
for entity in domain.entities:
    expected_fields = list(entity.fields.keys())
    expected[entity.table_name] = expected_fields

print(json.dumps({'expected': expected}, indent=2))

if not sqlite_path.exists():
    print(json.dumps({'error': 'db_not_found'}))
    raise SystemExit(0)

conn = sqlite3.connect(sqlite_path)
cur = conn.cursor()
actual = {}
for table in expected.keys():
    try:
        cur.execute(f"PRAGMA table_info({table})")
        cols = cur.fetchall()
        col_names = [c[1] for c in cols]
        actual[table] = col_names
    except Exception as e:
        actual[table] = {'error': str(e)}

print(json.dumps({'actual': actual}, indent=2))

# compute diffs
diffs = {}
for table, exp_cols in expected.items():
    act = actual.get(table)
    if isinstance(act, dict) and 'error' in act:
        diffs[table] = {'error': act['error']}
        continue
    missing = [c for c in exp_cols if c not in act]
    extra = [c for c in act if c not in exp_cols]
    diffs[table] = {'missing': missing, 'extra': extra}

print(json.dumps({'diffs': diffs}, indent=2))

conn.close()
