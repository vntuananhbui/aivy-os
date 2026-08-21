"""Research-session composition root for API, CLI/TUI and eval runners."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

from ai.research.orchestration.blueprint import SearchBlueprint
from ai.research.orchestration.models import ResearchModelBundle
from ai.research.orchestration.run_config import ResearchRunConfig
from ai.research.orchestration.session import SearchSession
from backend.infrastructure.research.telemetry import (
    FilesystemResearchTelemetryFactory,
)
from backend.infrastructure.research.workspace_factory import (
    FilesystemResearchWorkspaceFactory,
)
from searchos.config.settings import settings
from ai.skills.catalog.registry import SkillRegistry

_RESEARCH_MODEL_ROLES = (
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


def build_research_models(
    overrides: dict[str, BaseChatModel] | None = None,
) -> ResearchModelBundle:
    """Resolve configured role models outside the AI orchestration package."""
    from searchos.config.models import get_model_for

    replacements = overrides or {}
    models = {
        role: replacements.get(role) or get_model_for(role)
        for role in _RESEARCH_MODEL_ROLES
    }
    distribution: dict[str, dict[str, str]] = {}
    for role, model in models.items():
        profile_name = settings.roles.get(role, "")
        profile = settings.profiles.get(profile_name)
        model_name = (
            getattr(model, "model_name", None)
            or getattr(model, "model", None)
            or (profile.model if profile else "")
        )
        distribution[role] = {
            "profile": profile_name,
            "model": str(model_name),
            "provider": (
                profile.provider if profile else model.__class__.__name__
            ),
        }
    return ResearchModelBundle(models=models, distribution=distribution)


def create_research_session(
    *,
    blueprint: SearchBlueprint | None = None,
    skill_registry: SkillRegistry | None = None,
    workspace_root: str | None = None,
    skill_library_path: str = "",
    skill_global_library_path: str = "",
    generated_skill_library_path: str = "",
    skill_exclude: list[str] | None = None,
    model_overrides: dict[str, BaseChatModel] | None = None,
    skip_synthesis: bool | None = None,
    **session_overrides: Any,
) -> SearchSession:
    """Build a fully composed local-filesystem research session."""
    return SearchSession(
        models=build_research_models(model_overrides),
        run_config=ResearchRunConfig(
            enable_explore_batch=settings.enable_explore_batch,
            explore_min_waves=settings.explore_min_waves,
            explore_max_waves=settings.explore_max_waves,
            enable_skills=settings.enable_skills,
            enable_skill_router=settings.enable_skill_router,
            skill_router_top_k=settings.skill_router_top_k,
            orch_max_dispatches=settings.orch_max_dispatches,
            max_searches_per_sub_agent=settings.max_searches_per_sub_agent,
            enable_explore=settings.enable_explore,
            orch_max_iterations=settings.orch_max_iterations,
            orch_coverage_stall_rounds=settings.orch_coverage_stall_rounds,
            orch_trim_max_tokens=settings.orch_trim_max_tokens,
            orch_premature_end_max_resumes=(
                settings.orch_premature_end_max_resumes
            ),
            enable_access_skill_generation=(
                settings.enable_access_skill_generation
            ),
            access_skill_max_per_run=settings.access_skill_max_per_run,
            access_skill_min_opens=settings.access_skill_min_opens,
            access_skill_obs_chars=settings.access_skill_obs_chars,
        ),
        workspace_factory=FilesystemResearchWorkspaceFactory(),
        telemetry_factory=FilesystemResearchTelemetryFactory(),
        blueprint=blueprint,
        skill_registry=skill_registry,
        workspace_root=workspace_root or settings.workspace_root,
        skill_library_path=skill_library_path,
        skill_global_library_path=skill_global_library_path,
        generated_skill_library_path=(
            generated_skill_library_path
            or settings.generated_skill_library_path
        ),
        skill_exclude=skill_exclude,
        skip_synthesis=(
            settings.skip_synthesis
            if skip_synthesis is None
            else skip_synthesis
        ),
        **session_overrides,
    )


__all__ = ["build_research_models", "create_research_session"]
