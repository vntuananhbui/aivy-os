"""Thin httpx wrapper over the Jira REST endpoints this connector needs.

Cloud speaks API v3 and requires Atlassian Document Format (ADF) for
description/comment bodies; Server/Data Center speaks API v2 and accepts
plain strings there. ``JiraAuth.api_prefix`` picks the version; ``_body_text``
below picks the body shape — everything else (issue shape, transitions) is
close enough between the two that the rest of this client stays unbranched.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from connector.jira.auth import JiraAuth

logger = logging.getLogger(__name__)

ISSUE_FIELDS = "summary,status,issuetype,priority,assignee,reporter,description,updated,created,labels"


class JiraApiError(Exception):
    """A Jira REST call returned a non-2xx status."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


def _body_text(text: str, auth_mode: str) -> Any:
    """Plain text -> the shape Jira expects for description/comment ``body``.

    Cloud (v3) requires ADF; a bare string 400s. Server/DC (v2) wants the
    plain string directly. OAuth is also Cloud API v3 underneath, so it needs
    ADF too — same class of bug as ``search_jql``'s endpoint branch. This
    wraps ``text`` as a single ADF paragraph — enough for agent-authored
    descriptions/comments, not a full markup parser.
    """
    if auth_mode == "server":
        return text
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


def _adf_to_text(node: Any) -> str:
    """Best-effort flatten of an ADF document back to plain text for display —
    the inverse of ``_body_text``'s cloud branch. Server/DC issues already
    carry a plain string here, so this is a no-op for them."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_adf_to_text(child) for child in node.get("content", [])]
    joined = "".join(parts) if node.get("type") == "text" else " ".join(p for p in parts if p)
    if node.get("type") == "paragraph":
        return joined + "\n"
    return joined


class JiraClient:
    def __init__(self, auth: JiraAuth, timeout: float = 20.0):
        self._auth = auth
        self._timeout = timeout

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": self._auth.auth_header(), "Accept": "application/json"}
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(method, f"{self._auth.base_url}{path}", headers=headers, **kwargs)
        if resp.status_code >= 400:
            logger.warning("Jira %s %s -> %s: %s", method, path, resp.status_code, resp.text[:500])
            raise JiraApiError(f"Jira {method} {path} -> {resp.status_code}: {resp.text[:500]}", resp.status_code)
        logger.debug("Jira %s %s -> %s", method, path, resp.status_code)
        return resp.json() if resp.content else {}

    async def myself(self) -> dict:
        """Cheap call to confirm the credential works."""
        return await self._request("GET", f"{self._auth.api_prefix}/myself")

    async def search_jql(self, jql: str, max_results: int = 10) -> list[dict]:
        """Cloud uses the newer ``search/jql`` endpoint (the old ``/search``
        is deprecated there); Server/DC has no ``search/jql`` and must use
        the classic ``/search`` instead. OAuth is also Jira Cloud API v3
        underneath (just a different auth header) — it needs ``search/jql``
        too, not the classic endpoint."""
        prefix = self._auth.api_prefix
        if self._auth.auth_mode in ("cloud", "oauth"):
            data = await self._request(
                "POST", f"{prefix}/search/jql",
                json={"jql": jql, "maxResults": max_results, "fields": ISSUE_FIELDS.split(",")},
            )
        else:
            data = await self._request(
                "POST", f"{prefix}/search",
                json={"jql": jql, "maxResults": max_results, "fields": ISSUE_FIELDS.split(",")},
            )
        return data.get("issues", [])

    async def get_issue(self, key: str) -> dict:
        return await self._request(
            "GET", f"{self._auth.api_prefix}/issue/{key}",
            params={"fields": ISSUE_FIELDS},
        )

    async def create_issue(
        self, project: str, summary: str, description: str, issue_type: str, **extra_fields,
    ) -> dict:
        fields: dict[str, Any] = {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = _body_text(description, self._auth.auth_mode)
        fields.update(extra_fields)
        return await self._request("POST", f"{self._auth.api_prefix}/issue", json={"fields": fields})

    async def update_issue(self, key: str, **fields: Any) -> None:
        if "description" in fields and isinstance(fields["description"], str):
            fields["description"] = _body_text(fields["description"], self._auth.auth_mode)
        await self._request("PUT", f"{self._auth.api_prefix}/issue/{key}", json={"fields": fields})

    async def add_comment(self, key: str, text: str) -> dict:
        body = _body_text(text, self._auth.auth_mode)
        return await self._request(
            "POST", f"{self._auth.api_prefix}/issue/{key}/comment", json={"body": body},
        )

    async def list_transitions(self, key: str) -> list[dict]:
        data = await self._request("GET", f"{self._auth.api_prefix}/issue/{key}/transitions")
        return data.get("transitions", [])

    async def transition_issue(self, key: str, transition_id: str) -> None:
        await self._request(
            "POST", f"{self._auth.api_prefix}/issue/{key}/transitions",
            json={"transition": {"id": transition_id}},
        )
