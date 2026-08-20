"""Compatibility facade for backend research skill selection."""

from backend.application.research.skill_catalog import (
    SKILL_CATEGORIES,
    effective_skill_kwargs,
    normalize_access_only,
    skill_catalog,
    skill_enabled,
    skill_pools,
)

__all__ = [
    "SKILL_CATEGORIES",
    "effective_skill_kwargs",
    "normalize_access_only",
    "skill_catalog",
    "skill_enabled",
    "skill_pools",
]
