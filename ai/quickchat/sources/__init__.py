"""Generic "attached source" wiring for quickchat.

Reads the backend application's active-source capability list generically — the
prompt/priority-note logic in ``agent.py`` no longer hardcodes "sharepoint".

Tool *binding* stays per-connector-type (``_SOURCE_TOOLS`` below): a
connector's actual LangChain tools can't be derived generically from
``ConnectorBase`` alone (search/fetch aren't 1:1 with what a chat tool should
expose — see ``ai.adapters.connectors.sharepoint``'s citation-formatting,
pagination, etc.). Registering a new source's tools here is the one line a
future connector adds; everything else (priority note, parallel-search
instruction, active-check) is already generic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.application.connectors.capabilities import ConnectorSpec, list_active_sources


@dataclass(frozen=True)
class SourceTools:
    get_tools: Callable[[], list]
    # Name of the access skill (ai/skills/global/access/<name>/skill.md) whose
    # body gets pulled into the prompt alongside the generic priority note —
    # None if this source has no skill.md (falls back to the note alone).
    skill_name: str | None = None


def _sharepoint_tools() -> list:
    from ai.adapters.connectors.sharepoint import get_sharepoint_tools

    return get_sharepoint_tools()


def _jira_tools() -> list:
    from ai.adapters.connectors.jira import get_jira_tools

    return get_jira_tools()


_SOURCE_TOOLS: dict[str, SourceTools] = {
    "sharepoint": SourceTools(get_tools=_sharepoint_tools, skill_name="sharepoint"),
    "jira": SourceTools(get_tools=_jira_tools, skill_name="jira"),
}


def active_sources() -> list[ConnectorSpec]:
    return list_active_sources()


def tools_for_sources(sources: list[ConnectorSpec]) -> list:
    tools: list = []
    for source in sources:
        entry = _SOURCE_TOOLS.get(source.type)
        if entry is not None:
            tools.extend(entry.get_tools())
    return tools


def skill_name_for(source: ConnectorSpec) -> str | None:
    entry = _SOURCE_TOOLS.get(source.type)
    return entry.skill_name if entry is not None else None
