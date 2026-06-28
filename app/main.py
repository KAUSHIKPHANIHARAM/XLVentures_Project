"""
app/main.py

System entry point for the Enterprise Decision Intelligence Platform.

Usage:
    streamlit run app/main.py

    Or with a specific domain:
    ADIP_ACTIVE_DOMAIN=customer_management streamlit run app/main.py

This module:
    1. Ensures the project root is on sys.path.
    2. Delegates entirely to frontend/app.py (the Streamlit application).
    3. Acts as a clean, stable entry point — never hardcodes business logic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Project root = parent of this file's directory
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env if present (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass  # python-dotenv is optional

# Delegate to the Streamlit frontend application
# Streamlit re-imports this module on every rerun, so the import
# must be at module level (not inside __main__).
import frontend.app  # noqa: F401, E402 — side-effect import (runs Streamlit)
