"""LangChain tools for Jira; use cases live in the backend application layer."""

from __future__ import annotations

import json

from langchain_core.tools import tool
from loguru import logger

from backend.bootstrap.connectors import jira_access_service


async def _execute(function: str, **params):
    return await jira_access_service.execute(function, **params)


@tool
async def jira_search(query: str) -> str:
    """Search connected Jira issues using a JQL clause.

    Args:
        query: JQL such as ``text ~ "onboarding"``. Empty/``*`` lists recent issues.
    """
    result = await _execute("search", query=query)
    if not result.get("success"):
        return f"Error: {result.get('error')}"
    items = result["results"]
    if not items:
        return f"No Jira results for: {query}"
    lines = [f"Jira search: {query} ({len(items)} results)\n"]
    for index, item in enumerate(items):
        label = f"[{index}] {item['name']} (key={item['id']})"
        if item.get("snippet"):
            label += f" — {item['snippet']}"
        lines.append(label)
        if item.get("url"):
            lines.append(f"    {item['url']}")
    return "\n".join(lines)


@tool
async def jira_read(item_id: str, offset: int = 0) -> str:
    """Read a Jira issue by key, following continuation offsets for long issues.

    Args:
        item_id: Issue key returned by ``jira_search``.
        offset: Zero-based character offset, defaulting to the issue start.
    """
    result = await _execute("read", item_id=item_id, offset=offset)
    if not result.get("success"):
        return f"Error: {result.get('error')}"
    content = result["content"]
    next_offset = result.get("next_offset")
    if next_offset is not None:
        content += (
            f"\n\n[... {result['total_chars'] - next_offset} more chars available — "
            f"call jira_read(item_id={item_id!r}, offset={next_offset}) to continue]"
        )
    return content


@tool
async def jira_create_issue(project: str, summary: str, issue_type: str, description: str = "") -> str:
    """Create a Jira issue after the user's create intent is unambiguous.

    Args:
        project: Jira project key.
        summary: Issue title.
        issue_type: Existing issue type such as Task, Bug or Story.
        description: Optional plain-text description.
    """
    result = await _execute(
        "create_issue", project=project, summary=summary,
        issue_type=issue_type, description=description,
    )
    if not result.get("success"):
        return f"Error: {result.get('error')}"
    return f"Created {result['key']}: {result['url']}"


@tool
async def jira_update_issue(key: str, fields_json: str) -> str:
    """Update Jira issue fields from a JSON object.

    Args:
        key: Jira issue key.
        fields_json: JSON object containing Jira field updates.
    """
    try:
        fields = json.loads(fields_json)
    except json.JSONDecodeError as exc:
        return f"Error: fields_json is not valid JSON: {exc}"
    if not isinstance(fields, dict):
        return "Error: fields_json must decode to a JSON object."
    result = await _execute("update_issue", key=key, fields=fields)
    if not result.get("success"):
        return f"Error: {result.get('error')}"
    return f"Updated {result['key']}."


@tool
async def jira_add_comment(key: str, text: str) -> str:
    """Add a plain-text comment to a Jira issue.

    Args:
        key: Jira issue key.
        text: Comment body.
    """
    result = await _execute("add_comment", key=key, text=text)
    if not result.get("success"):
        return f"Error: {result.get('error')}"
    return f"Commented on {result['key']}."


@tool
async def jira_transition_issue(key: str, transition_name: str) -> str:
    """Execute a named Jira workflow transition.

    Args:
        key: Jira issue key.
        transition_name: Exact transition name available on the issue.
    """
    result = await _execute("transition_issue", key=key, transition_name=transition_name)
    if not result.get("success"):
        return f"Error: {result.get('error')}"
    return f"{result['key']} -> {result['status']}."


def get_jira_tools() -> list:
    return [
        jira_search,
        jira_read,
        jira_create_issue,
        jira_update_issue,
        jira_add_comment,
        jira_transition_issue,
    ]


__all__ = [
    "get_jira_tools",
    "jira_add_comment",
    "jira_create_issue",
    "jira_read",
    "jira_search",
    "jira_transition_issue",
    "jira_update_issue",
]
