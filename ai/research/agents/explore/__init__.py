"""Explore agent (paper §Agent Roles) — pre-search information-landscape scout.

Dispatched before search begins so the orchestrator can map where data lives
and plan a strategy. No extraction middleware attaches: its only output is the
final briefing message (see ``agent.md``).
"""

from __future__ import annotations

AGENT_TYPE = "explore_agent"


def get_tools(skill_names: list[str] | None = None) -> list:
    """根据开关选择并发覆盖波次或旧版串行浏览工具。"""
    from searchos.config.settings import settings
    from searchos.tools.simple_browser import explore_web, get_simple_browser_tools

    from ai.adapters.connectors.sharepoint import get_sharepoint_tools
    from ai.adapters.connectors.jira import get_jira_tools
    from connector.registry import is_source_active

    tools = [explore_web] if settings.enable_explore_batch else list(get_simple_browser_tools())
    if is_source_active("sharepoint"):
        tools.extend(get_sharepoint_tools())
    if is_source_active("jira"):
        tools.extend(get_jira_tools())
    return tools
