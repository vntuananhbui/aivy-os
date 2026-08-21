"""Compatibility facade for the relocated Jira AI tools.

New AI code should import :mod:`ai.adapters.connectors.jira` directly.
"""

from ai.adapters.connectors.jira import (
    get_jira_tools,
    jira_add_comment,
    jira_create_issue,
    jira_read,
    jira_search,
    jira_transition_issue,
    jira_update_issue,
)
from backend.bootstrap.connectors import connector_capability_reader


def is_configured() -> bool:
    """Legacy synchronous capability check used while graphs are built."""
    return connector_capability_reader.is_connected("jira")


__all__ = [
    "get_jira_tools",
    "is_configured",
    "jira_add_comment",
    "jira_create_issue",
    "jira_read",
    "jira_search",
    "jira_transition_issue",
    "jira_update_issue",
]
