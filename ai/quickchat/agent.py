"""Builds the plain chat agent graph."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

from ai.common.temporal import render_temporal_grounding
from ai.quickchat import prompts
from ai.quickchat.persistence.checkpointer import get_checkpointer
from ai.quickchat.tools import get_chat_tools
from searchos.config.models import get_model_for, resolve_profile


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_QUICKCHAT_SKILL_ROOTS = (
    _REPOSITORY_ROOT / "ai" / "skills" / "global",
    _REPOSITORY_ROOT / "ai" / "skills" / "quickchat",
)

_skill_registry = None  # lazy SkillRegistry; load_directory() is mtime-cached per root


def _load_access_skills():
    """Load every access skill quickchat can see: ``ai/skills/global`` (shared
    with deep-research — aivy_search_stock, sharepoint, ...) and ``ai/skills/quickchat``
    (quickchat-only skills, currently empty — reserved for later)."""
    from ai.skills.catalog.registry import SkillRegistry

    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    for root in _QUICKCHAT_SKILL_ROOTS:
        if root.exists():
            _skill_registry.load_directory(root)
    return _skill_registry


def _attached_source_prompt(source, *, web_search_enabled: bool) -> str:
    """Priority note + (if the source has one) its access skill's body —
    generic over any ``ConnectorSpec``, not hardcoded to sharepoint. Missing
    or malformed skill.md falls back to the note alone rather than breaking
    chat (see ai.quickchat.sources.skill_name_for)."""
    from ai.skills.core.models import SkillCategory
    from ai.quickchat.sources import skill_name_for

    note = prompts.attached_source_priority_note(source.display_name, web_search_enabled=web_search_enabled)
    skill_name = skill_name_for(source)
    if skill_name is None:
        return note
    try:
        registry = _load_access_skills()
        skill = registry.get(skill_name)
        if skill is None or skill.meta.category != SkillCategory.ACCESS:
            raise LookupError(f"{skill_name} skill not found under ai/skills/global")
        return f"{note}\n\n{skill.body}"
    except Exception as exc:  # missing/malformed skill file shouldn't break chat
        logger.warning("quickchat: failed to load {} skill.md, using note only: {}", skill_name, exc)
        return note


def _skill_prompt_addendum(*, sources: list, web_search_enabled: bool) -> str:
    """Pull attached-source instructions (generic, one per active connector)
    plus the always-on ``aivy_search_stock`` skill — straight from skill.md,
    the same files the deep-research orchestrator dispatches through, so
    quickchat doesn't carry its own drifted copy of the rules.

    Only skills wired to a real quickchat tool belong here (see
    ``ai/quickchat/tools.py::get_chat_tools`` / ``ai/quickchat/sources/``) — a
    future quickchat-only skill needs its own tool wired there first.
    """
    from ai.skills.core.models import SkillCategory

    registry = _load_access_skills()
    parts: list[str] = [
        _attached_source_prompt(source, web_search_enabled=web_search_enabled) for source in sources
    ]
    if len(sources) > 1:
        parts.append(prompts.PARALLEL_SOURCES_NOTE)

    try:
        skill = registry.get("aivy_search_stock")
        if skill is None or skill.meta.category != SkillCategory.ACCESS:
            raise LookupError("aivy_search_stock skill not found under ai/skills/global")
        parts.append("You also have aivy_search_stock(symbols). " + skill.body)
    except Exception as exc:
        logger.warning("quickchat: failed to load aivy_search_stock skill.md: {}", exc)

    if not parts:
        return ""
    return "\n\n" + "\n\n".join(parts)


def _build_system_prompt(current_date: str, *, sources: list, web_search_enabled: bool) -> str:
    prompt = f"{prompts.base_system_prompt(web_search_enabled=web_search_enabled)}\n\n{render_temporal_grounding(current_date, 'chat')}"
    prompt += _skill_prompt_addendum(sources=sources, web_search_enabled=web_search_enabled)
    return prompt


def current_date_str() -> str:
    """Today's Vietnam date — prompt grounding and daily graph cache-bust key."""
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()

# Effort only means something to chat while thinking is on: it maps to the
# `reasoning_effort` request param, which controls how deep the model reasons
# before answering — independent of max_tokens (that only caps output *length*
# and would truncate a reasoning model mid-thought if used for this).
# Two validation layers disagree on the accepted enum (Azure's own gateway:
# none/minimal/low/medium/high; the sglang backend behind it: none/low/medium/
# high/max) — "high" is the safe ceiling that passes both, so "max" clamps to it.
CHAT_EFFORT_TO_REASONING: dict[str, str] = {
    "low": "low", "medium": "medium", "high": "high", "max": "high",
}

def build_chat_agent(*, thinking: bool = True, effort: str = "medium", web_search_enabled: bool = True):
    from langchain.agents import create_agent

    from ai.quickchat.middleware import build_middleware_stack
    from ai.quickchat.sources import active_sources

    # Only send reasoning_effort to models the admin has actually marked as
    # thinking-capable (enable_thinking=True on the card) — a non-reasoning
    # model bound to "chat" would 400 on an unrecognized param otherwise, the
    # same failure mode as the chat_template_kwargs mismatch this replaces.
    reasoning_effort = None
    if resolve_profile("chat").enable_thinking:
        reasoning_effort = CHAT_EFFORT_TO_REASONING.get(effort, "low") if thinking else "none"
    sources = active_sources()
    tools = get_chat_tools(effort, sources=sources, web_search_enabled=web_search_enabled)
    logger.info(
        "quickchat.build_chat_agent: sources={} tools={}",
        [s.type for s in sources], [getattr(t, "name", t) for t in tools],
    )
    return create_agent(
        model=get_model_for("chat", reasoning_effort=reasoning_effort),
        tools=tools,
        system_prompt=_build_system_prompt(current_date_str(), sources=sources, web_search_enabled=web_search_enabled),
        checkpointer=get_checkpointer(),
        middleware=build_middleware_stack(role="chat"),
    )
