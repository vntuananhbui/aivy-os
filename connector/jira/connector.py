"""Wires Jira credentials + the REST client into the ``ConnectorBase``
interface. Read side (search/fetch) satisfies ``ConnectorBase``; write side
(create/update/comment/transition) is Jira-specific and lives as extra
methods here rather than on the base — no other connector needs them."""

from __future__ import annotations

from loguru import logger

from connector import cache
from connector.base import ConnectorBase, ConnectorItem, ConnectorStatus
from connector.jira.auth import JiraAuth
from connector.jira.client import JiraClient, _adf_to_text

SOURCE = "jira"


def _issue_url(site_url: str, key: str) -> str:
    return f"{site_url}/browse/{key}"


class JiraConnector(ConnectorBase):
    def __init__(
        self,
        site_url: str,
        auth_mode: str,
        *,
        email: str = "",
        api_token: str = "",
        personal_access_token: str = "",
        access_token: str = "",
        expires_at: float | None = None,
        cloud_id: str = "",
        project_keys: list[str] | None = None,
    ):
        self._auth = JiraAuth(
            site_url, auth_mode,
            email=email, api_token=api_token, personal_access_token=personal_access_token,
            access_token=access_token, expires_at=expires_at, cloud_id=cloud_id,
        )
        self._client = JiraClient(self._auth)
        self._project_keys = project_keys or []

    async def connect(self) -> ConnectorStatus:
        me = await self._client.myself()
        name = me.get("displayName") or me.get("name") or "unknown user"
        return ConnectorStatus(connected=True, detail=f"Jira OK ({name})")

    def _scoped_jql(self, query: str) -> str:
        """``query`` is a JQL clause the caller composes (e.g. ``text ~
        "keyword"``, ``project = KAN``, ``key ~ "KAN-*"``) — passed through
        as-is, not auto-wrapped in ``text ~ "..."``. Wrapping it used to
        silently turn a real clause like ``project = AIVY`` into a literal
        text search for the string "project = AIVY", which never matches
        anything. Project scope (if configured) is AND'd on top."""
        clauses = []
        if self._project_keys:
            keys = ", ".join(f'"{k}"' for k in self._project_keys)
            clauses.append(f"project in ({keys})")
        if query and query.strip() not in ("", "*"):
            clauses.append(f"({query.strip()})")
        return " AND ".join(clauses) + " ORDER BY updated DESC" if clauses else "ORDER BY updated DESC"

    async def search(self, query: str, max_results: int = 10) -> list[ConnectorItem]:
        jql = self._scoped_jql(query)
        logger.debug("jira.connector.search: jql={!r} max_results={}", jql, max_results)
        issues = await self._client.search_jql(jql, max_results)
        logger.debug("jira.connector.search: {} issue(s)", len(issues))
        items = []
        for issue in issues:
            fields = issue.get("fields", {})
            status = (fields.get("status") or {}).get("name", "")
            issue_type = (fields.get("issuetype") or {}).get("name", "")
            items.append(ConnectorItem(
                id=issue.get("key", ""),
                title=fields.get("summary", ""),
                url=_issue_url(self._auth.site_url, issue.get("key", "")),
                snippet=f"{issue_type} — {status}",
            ))
        return items

    async def fetch(self, item_id: str) -> str:
        """Text content of an issue, prefixed with a citation header (key +
        title + URL). Cached by ``(item_id, updated)`` — Jira issues change
        far more often than SharePoint files, so freshness is checked on
        every call via a cheap metadata-bearing fetch rather than skipped."""
        issue = await self._client.get_issue(item_id)
        fields = issue.get("fields", {})
        title = fields.get("summary", "")
        updated = fields.get("updated", "")
        url = _issue_url(self._auth.site_url, item_id)
        header = f"# [{item_id}] {title}\n{url}\n\n"

        cached = await cache.get(SOURCE, item_id)
        if cached is not None and cached.last_modified == updated:
            logger.debug("jira.connector.fetch: item_id={!r} cache HIT", item_id)
            return header + cached.content

        status = (fields.get("status") or {}).get("name", "")
        issue_type = (fields.get("issuetype") or {}).get("name", "")
        priority = (fields.get("priority") or {}).get("name", "")
        assignee = (fields.get("assignee") or {}).get("displayName", "unassigned")
        reporter = (fields.get("reporter") or {}).get("displayName", "")
        labels = ", ".join(fields.get("labels") or [])
        description = _adf_to_text(fields.get("description")).strip()

        lines = [
            f"Type: {issue_type}", f"Status: {status}", f"Priority: {priority}",
            f"Assignee: {assignee}", f"Reporter: {reporter}",
        ]
        if labels:
            lines.append(f"Labels: {labels}")
        lines.append("")
        lines.append(description or "(no description)")
        content = "\n".join(lines)

        await cache.put(SOURCE, item_id, title, content, updated)
        logger.debug("jira.connector.fetch: item_id={!r} downloaded, {} chars", item_id, len(content))
        return header + content

    async def create_issue(
        self, project: str, summary: str, description: str, issue_type: str,
    ) -> ConnectorItem:
        issue = await self._client.create_issue(project, summary, description, issue_type)
        key = issue.get("key", "")
        logger.info("jira.connector.create_issue: project={!r} key={!r}", project, key)
        return ConnectorItem(id=key, title=summary, url=_issue_url(self._auth.site_url, key))

    async def update_issue(self, key: str, **fields) -> None:
        await self._client.update_issue(key, **fields)
        await cache.purge(SOURCE, [key])
        logger.info("jira.connector.update_issue: key={!r} fields={}", key, list(fields))

    async def add_comment(self, key: str, text: str) -> None:
        await self._client.add_comment(key, text)
        await cache.purge(SOURCE, [key])
        logger.info("jira.connector.add_comment: key={!r}", key)

    async def transition_issue(self, key: str, transition_name: str) -> str:
        transitions = await self._client.list_transitions(key)
        match = next(
            (t for t in transitions if t.get("name", "").lower() == transition_name.lower()), None,
        )
        if match is None:
            available = ", ".join(t.get("name", "") for t in transitions)
            raise ValueError(f"No transition named {transition_name!r} on {key}. Available: {available}")
        await self._client.transition_issue(key, match["id"])
        await cache.purge(SOURCE, [key])
        logger.info("jira.connector.transition_issue: key={!r} -> {!r}", key, transition_name)
        return match.get("to", {}).get("name", transition_name)
