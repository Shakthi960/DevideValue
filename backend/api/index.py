"""
Vercel serverless function entry point.

Exposes the FastAPI app so Vercel's Python runtime can serve
the Device Valuation Platform API from /api/*.
"""

import os
import sys

# Make the backend package importable from this file's location.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.main import app  # noqa: E402

handler = app