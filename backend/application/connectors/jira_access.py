"""Jira content and mutation use cases, independent from AI tool formatting."""

from __future__ import annotations

from typing import Any, Callable

from backend.application.connectors.repositories import JiraConnectionRepository
from connector.jira.auth import JiraAuthError
from connector.jira.client import JiraApiError
from connector.jira.connector import JiraConnector

_JIRA_ERRORS = (JiraApiError, JiraAuthError, ValueError)


class JiraAccessService:
    MAX_READ_CHARS = 8000

    def __init__(
        self,
        repository: JiraConnectionRepository,
        connector_factory: Callable[..., JiraConnector] = JiraConnector,
    ) -> None:
        self._repository = repository
        self._connector_factory = connector_factory

    async def _connector(self) -> JiraConnector | None:
        status = await self._repository.status()
        credential = await self._repository.get_credential()
        if not status or not status.get("connected") or credential is None:
            return None
        return self._connector_factory(
            credential.site_url,
            credential.auth_mode,
            email=credential.email,
            api_token=credential.api_token,
            personal_access_token=credential.personal_access_token,
            access_token=credential.access_token,
            expires_at=credential.expires_at,
            cloud_id=credential.cloud_id,
            project_keys=list(status.get("project_keys") or []),
        )

    async def execute(self, function: str, **params: Any) -> dict[str, Any]:
        valid_functions = [
            "search",
            "read",
            "create_issue",
            "update_issue",
            "add_comment",
            "transition_issue",
        ]
        if function not in valid_functions:
            return {
                "success": False,
                "error": f"Unknown function: {function}",
                "valid_functions": valid_functions,
            }
        if function == "read" and not params.get("item_id"):
            return {"success": False, "error": "Missing required parameter: item_id"}

        connector = await self._connector()
        if connector is None:
            return {"success": False, "error": "Jira connector not configured or not connected."}
        try:
            if function == "search":
                items = await connector.search(params.get("query", ""))
                return {"success": True, "results": [
                    {"id": item.id, "name": item.title, "url": item.url, "snippet": item.snippet}
                    for item in items
                ]}
            if function == "read":
                item_id = params.get("item_id", "")
                content = await connector.fetch(item_id)
                offset = max(0, int(params.get("offset", 0) or 0))
                chunk = content[offset : offset + self.MAX_READ_CHARS]
                next_offset = offset + len(chunk)
                return {"success": True, "content": chunk, "total_chars": len(content), "next_offset": next_offset if next_offset < len(content) else None}
            if function == "create_issue":
                project, summary, issue_type = params.get("project", ""), params.get("summary", ""), params.get("issue_type", "")
                if not (project and summary and issue_type):
                    return {"success": False, "error": "Missing required parameter(s): project, summary, issue_type"}
                item = await connector.create_issue(project, summary, params.get("description", ""), issue_type)
                return {"success": True, "key": item.id, "url": item.url}
            if function == "update_issue":
                key, fields = params.get("key", ""), params.get("fields") or {}
                if not key or not fields:
                    return {"success": False, "error": "Missing required parameter(s): key, fields"}
                await connector.update_issue(key, **fields)
                return {"success": True, "key": key}
            if function == "add_comment":
                key, text = params.get("key", ""), params.get("text", "")
                if not (key and text):
                    return {"success": False, "error": "Missing required parameter(s): key, text"}
                await connector.add_comment(key, text)
                return {"success": True, "key": key}
            if function == "transition_issue":
                key, transition = params.get("key", ""), params.get("transition_name", "")
                if not (key and transition):
                    return {"success": False, "error": "Missing required parameter(s): key, transition_name"}
                status_name = await connector.transition_issue(key, transition)
                return {"success": True, "key": key, "status": status_name}
        except _JIRA_ERRORS as exc:
            return {"success": False, "error": str(exc)}
        raise AssertionError(f"Unhandled Jira access function: {function}")
