"""
app/main.py

System entry point for the Enterprise Decision Intelligence Platform.

Usage:
    streamlit run app/main.py

    Or with a specific domain:
    ADIP_ACTIVE_DOMAIN=customer_management streamlit run app/main.py

This module:
    1. Ensures the project root is on sys.path.
    2. Loads the .env file for local development.
    3. The actual Streamlit UI code lives in frontend/app.py and is run
       by Streamlit directly through sys.argv redirection — NOT via import.
       Importing frontend/app.py as a module would cause it to execute
       its top-level Streamlit calls twice, breaking the page.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# -----------------------------------------------------------------------
# 1. Put the project root on sys.path so all internal packages resolve
# -----------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# -----------------------------------------------------------------------
# 2. Load .env (local development only — never fails if file absent)
# -----------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env", override=True)
except ImportError:
    pass  # python-dotenv is optional; env vars may already be set

# -----------------------------------------------------------------------
# 3. Re-execute Streamlit targeting frontend/app.py directly.
#    We achieve this by replacing sys.argv[0] with the real app file
#    and then exec-ing it — so Streamlit only sees one script, not two.
#    This avoids the double-execution bug caused by `import frontend.app`.
# -----------------------------------------------------------------------
_APP_FILE = str(_PROJECT_ROOT / "frontend" / "app.py")

# Update argv so that any relative path resolution inside app.py still works
sys.argv[0] = _APP_FILE

# exec the real app file in the current module's global namespace.
# Streamlit has already started and is watching THIS file (app/main.py),
# so we hand off execution to frontend/app.py here.
with open(_APP_FILE, "r", encoding="utf-8") as _f:
    exec(compile(_f.read(), _APP_FILE, "exec"), {"__file__": _APP_FILE, "__name__": "__main__"})
