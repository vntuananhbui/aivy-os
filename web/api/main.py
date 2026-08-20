"""Compatibility entry point for the migrated backend application.

The existing ``uvicorn api.main:app --app-dir web`` command remains valid
during migration. New deployment code should target ``backend.api.main:app``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.api.main import app, create_app, lifespan  # noqa: E402,F401
