"""Thin httpx wrapper over the Microsoft Graph REST endpoints SharePoint needs.

Everything targets the signed-in user's own drive (``/me/drive/...``) — no
site resolution. Returns plain dicts/strings — no framework coupling,
mirroring ``tools/backend/base.py``'s small-return-type convention.
"""

from __future__ import annotations

import logging

import httpx

from backend.infrastructure.connectors.sharepoint.auth import SharePointAuth

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

CHILDREN_SELECT = "id,name,folder,file,webUrl,size"


class SharePointGraphError(Exception):
    """A Graph REST call returned a non-2xx status."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class SharePointClient:
    def __init__(self, auth: SharePointAuth, timeout: float = 20.0):
        self._auth = auth
        self._timeout = timeout

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        token = await self._auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(method, f"{GRAPH_BASE}{path}", headers=headers, **kwargs)
        if resp.status_code >= 400:
            logger.warning("Graph %s %s -> %s: %s", method, path, resp.status_code, resp.text[:500])
            raise SharePointGraphError(f"Graph {method} {path} -> {resp.status_code}: {resp.text[:500]}", resp.status_code)
        logger.debug("Graph %s %s -> %s", method, path, resp.status_code)
        return resp.json() if resp.content else {}

    async def get_drive_root(self) -> dict:
        """Cheap call to confirm the token works and the user has a drive."""
        return await self._request("GET", "/me/drive/root")

    def _item_path(self, item_id: str) -> tuple[str, str]:
        """Split a possibly drive-qualified id (``"{driveId}:{itemId}"``,
        produced by ``search_scoped``) into (API path prefix, raw item id).

        ``/search/query`` searches the whole Microsoft Search index, which can
        surface items from a drive other than the signed-in user's own
        ``/me/drive`` (e.g. a shared site's document library). Calling
        ``/me/drive/items/{id}`` for such an item 404s even though the id is
        perfectly valid — it just belongs to a different drive. Plain ids
        (from ``list_children``/``search_drive``, always ``/me/drive``-scoped
        already) pass through unchanged.
        """
        drive_id, sep, real_id = item_id.partition(":")
        if sep and drive_id:
            return f"/drives/{drive_id}", real_id
        return "/me/drive", item_id

    async def get_item_metadata(self, item_id: str) -> dict:
        prefix, real_id = self._item_path(item_id)
        return await self._request(
            "GET", f"{prefix}/items/{real_id}",
            params={"$select": "id,name,webUrl,lastModifiedDateTime"},
        )

    async def list_children(self, folder_id: str | None = None) -> list[dict]:
        path = f"/me/drive/items/{folder_id}/children" if folder_id else "/me/drive/root/children"
        data = await self._request("GET", path, params={"$select": CHILDREN_SELECT, "$top": 200})
        return data.get("value", [])

    async def search_drive(self, query: str, max_results: int = 10) -> list[dict]:
        data = await self._request(
            "GET", f"/me/drive/root/search(q='{query}')",
            params={"$top": max_results},
        )
        return data.get("value", [])[:max_results]

    async def search_scoped(self, query: str, folder_urls: list[str], max_results: int = 20) -> list[dict]:
        """Full-text search (filename AND content, via the Microsoft Search
        index — not a live crawl) scoped to one or more folders by KQL
        ``path:`` terms. Used when the picked scope is a whole folder instead
        of a short explicit file list, so hundreds of files never get dumped
        into the agent's context — the index does the narrowing.

        ``isDocument:true`` excludes folders themselves from hits (Graph
        docs' Example 5). Per Graph's documented behavior a bare wildcard
        doesn't work for driveItem search, so an empty ``query`` just omits
        the free-text term and keeps the path/isDocument filters.
        """
        path_clause = " OR ".join(f'path:"{u}"' for u in folder_urls if u)
        terms = " ".join(t for t in (query.strip(), "isDocument:true", f"({path_clause})" if path_clause else "") if t)
        body = {
            "requests": [
                {
                    "entityTypes": ["driveItem"],
                    "query": {"queryString": terms},
                    "size": min(max(max_results, 1), 500),
                    "fields": ["id", "name", "webUrl", "parentReference"],
                }
            ]
        }
        token = await self._auth.get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{GRAPH_BASE}/search/query", headers=headers, json=body)
        if resp.status_code >= 400:
            logger.warning("Graph POST /search/query -> %s: %s", resp.status_code, resp.text[:500])
            raise SharePointGraphError(f"Graph POST /search/query -> {resp.status_code}: {resp.text[:500]}", resp.status_code)
        logger.debug("Graph POST /search/query -> %s (queryString=%r)", resp.status_code, terms)
        data = resp.json()
        hits = (data.get("value") or [{}])[0].get("hitsContainers") or [{}]
        results = []
        for hit in hits[0].get("hits", []):
            resource = hit.get("resource") or {}
            item_id = resource.get("id", "")
            # The search index spans every drive the user can see, not just
            # /me/drive — qualify the id with its driveId (when present) so
            # get_item_metadata/fetch_item_bytes route to the right drive
            # instead of 404ing against /me/drive for a cross-drive hit.
            drive_id = (resource.get("parentReference") or {}).get("driveId", "")
            results.append({
                "id": f"{drive_id}:{item_id}" if drive_id else item_id,
                "name": resource.get("name", ""),
                "webUrl": resource.get("webUrl", ""),
                "summary": hit.get("summary", ""),
            })
        return results

    async def fetch_item_bytes(self, item_id: str) -> bytes:
        """Raw file content. ``/content`` 302s to the actual download URL (a
        SharePoint CDN link) — httpx does NOT follow redirects by default, so
        without ``follow_redirects=True`` this silently returns an empty body
        instead of the file."""
        prefix, real_id = self._item_path(item_id)
        token = await self._auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{GRAPH_BASE}{prefix}/items/{real_id}/content"
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            logger.warning("Graph GET %s/content -> %s: %s", item_id, resp.status_code, resp.text[:500])
            raise SharePointGraphError(f"Graph GET {url} -> {resp.status_code}: {resp.text[:500]}", resp.status_code)
        logger.debug("Graph GET %s/content -> %s (%s bytes)", item_id, resp.status_code, len(resp.content))
        return resp.content
