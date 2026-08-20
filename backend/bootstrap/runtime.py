"""Dependency injection — LLM, SearchProvider, shared state."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from backend.application.research_runs.service import ResearchRunService
from backend.infrastructure.research_runs.memory import InMemoryResearchRunRepository

# Repository root (backend/bootstrap/runtime.py → parent×3).
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Load .env from repo root
_env_path = _REPO_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def get_llm(model: str | None = None):
    from searchos.config.models import get_model_for

    return get_model_for(model or "judge")


def init_search_provider(name: str | None = None):
    # SearchOS binds search + page-fetch onto one shared browser provider.
    # An explicit ``name`` (from web settings) wins; otherwise same resolution
    # as the CLI: SF_SEARCH_PROVIDER, else infer from available keys
    # (serper → tavily), else the ragflow fallback.
    from searchos.tools.simple_browser.state import set_browser_provider
    from tools.search import build_search_provider

    set_browser_provider(build_search_provider(name or ""))


WORKSPACE_ROOT = os.environ.get("SF_WORKSPACE_ROOT", str(_REPO_ROOT / "searchos_workspace"))

# Web settings overlay — next to .env, NOT inside WORKSPACE_ROOT (whose
# subdirectories are scanned as durable research runs by history.py).
WEB_SETTINGS_PATH = os.environ.get("SF_WEB_SETTINGS_PATH", str(_REPO_ROOT / "web_settings.json"))

# The .env file web-set keys/provider knobs are persisted to. SF_ENV_FILE
# exists so tests can point writes at a tmp path.
ENV_FILE_PATH = os.environ.get("SF_ENV_FILE", str(_REPO_ROOT / ".env"))

# Current single-process adapter. The application service is the sole source
# of live research-run lifecycle state.
research_run_repository = InMemoryResearchRunRepository()
research_run_service = ResearchRunService(research_run_repository)
