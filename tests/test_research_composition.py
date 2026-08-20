from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from ai.research.orchestration.models import ResearchModelBundle
from ai.research.orchestration.run_config import ResearchRunConfig
from ai.research.orchestration.session import SearchSession
from ai.research.telemetry.ports import InMemoryResearchTelemetryFactory
from backend.bootstrap.research import build_research_models
from backend.infrastructure.research.workspace_factory import (
    FilesystemResearchWorkspaceFactory,
)

ROLES = (
    "orchestrator",
    "judge",
    "extraction",
    "alias_resolver",
    "synthesis",
    "skill_evolver",
    "post_mortem",
    "sub_agent",
    "skill_runtime",
)


def _fake_models() -> dict[str, FakeListChatModel]:
    return {role: FakeListChatModel(responses=[role]) for role in ROLES}


def _run_config() -> ResearchRunConfig:
    return ResearchRunConfig(
        enable_explore_batch=True,
        explore_min_waves=1,
        explore_max_waves=2,
        enable_skills=False,
        enable_skill_router=False,
        skill_router_top_k=0,
        orch_max_dispatches=2,
        max_searches_per_sub_agent=3,
        enable_explore=True,
        orch_max_iterations=4,
        orch_coverage_stall_rounds=2,
        orch_trim_max_tokens=1000,
        orch_premature_end_max_resumes=1,
        enable_access_skill_generation=False,
        access_skill_max_per_run=0,
        access_skill_min_opens=0,
        access_skill_obs_chars=0,
    )


def test_model_bundle_is_immutable_and_requires_explicit_roles() -> None:
    models = _fake_models()
    bundle = ResearchModelBundle(models=models, distribution={})

    assert bundle.require("orchestrator") is models["orchestrator"]
    with pytest.raises(TypeError):
        bundle.models["orchestrator"] = models["judge"]  # type: ignore[index]
    with pytest.raises(ValueError, match="Missing research model"):
        bundle.require("missing")


def test_search_session_accepts_pre_resolved_models_without_model_factory(
    tmp_path,
) -> None:
    bundle = ResearchModelBundle(models=_fake_models(), distribution={})

    session = SearchSession(
        models=bundle,
        run_config=_run_config(),
        workspace_factory=FilesystemResearchWorkspaceFactory(),
        telemetry_factory=InMemoryResearchTelemetryFactory(),
        workspace_root=str(tmp_path),
        skip_synthesis=True,
    )

    assert session._model is bundle.require("orchestrator")
    assert session._model_distribution == {}


def test_backend_bootstrap_honors_complete_model_overrides() -> None:
    overrides = _fake_models()

    bundle = build_research_models(overrides)

    assert all(bundle.require(role) is overrides[role] for role in ROLES)
