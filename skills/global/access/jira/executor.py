"""Jira access-skill adapter over the backend application service."""

from __future__ import annotations

from typing import Any

from backend.bootstrap.connectors import jira_access_service


async def execute(params: dict[str, Any], ctx: Any = None) -> dict[str, Any]:
    function = params.get("function", "")
    return await jira_access_service.execute(
        function,
        **{key: value for key, value in params.items() if key != "function"},
    )
