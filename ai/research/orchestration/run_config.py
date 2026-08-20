"""Immutable per-run configuration consumed by ``SearchSession``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchRunConfig:
    enable_explore_batch: bool
    explore_min_waves: int
    explore_max_waves: int
    enable_skills: bool
    enable_skill_router: bool
    skill_router_top_k: int
    orch_max_dispatches: int
    max_searches_per_sub_agent: int
    enable_explore: bool
    orch_max_iterations: int
    orch_coverage_stall_rounds: int
    orch_trim_max_tokens: int
    orch_premature_end_max_resumes: int
    enable_access_skill_generation: bool
    access_skill_max_per_run: int
    access_skill_min_opens: int
    access_skill_obs_chars: int


__all__ = ["ResearchRunConfig"]
