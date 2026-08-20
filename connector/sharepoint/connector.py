"""Wires delegated (pasted-token) auth + the Graph client into the
``ConnectorBase`` interface. Targets the signed-in user's own drive."""

from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit, urlunsplit

from loguru import logger

from connector import cache
from connector.base import ConnectorBase, ConnectorItem, ConnectorStatus
from connector.sharepoint.auth import SharePointAuth
from connector.sharepoint.client import SharePointClient
from connector.sharepoint.parse import extract_text

SOURCE = "sharepoint"


def browser_url(web_url: str) -> str:
    """Turn Graph's direct OneDrive path into the browser UI route.

    Some enterprise tenants return a valid ``webUrl`` whose ``/personal/...``
    path is usable by Graph but returns 404 when navigated to directly. Their
    web UI opens the same item through ``/my?id=...&parent=...`` instead.
    ``viewid`` is intentionally omitted: it controls the folder view, while
    ``id`` and ``parent`` identify the item and are sufficient for navigation.
    """
    if not web_url:
        return web_url
    parsed = urlsplit(web_url)
    if not parsed.netloc.endswith("-my.sharepoint.com") or not parsed.path.startswith(
        "/personal/"
    ):
        return web_url

    item_path = unquote(parsed.path)
    parent_path, separator, _ = item_path.rpartition("/")
    if not separator:
        return web_url
    query = f"id={quote(item_path, safe='')}&parent={quote(parent_path, safe='')}"
    return urlunsplit((parsed.scheme, parsed.netloc, "/my", query, ""))


class SharePointConnector(ConnectorBase):
    def __init__(self, access_token: str):
        auth = SharePointAuth(access_token)
        self._auth = auth
        self._client = SharePointClient(auth)

    @property
    def token_expires_at(self) -> float | None:
        return self._auth.expires_at

    async def connect(self) -> ConnectorStatus:
        root = await self._client.get_drive_root()
        return ConnectorStatus(connected=True, detail=f"drive OK ({root.get('name', 'root')})")

    async def list_folder(self, folder_id: str | None = None) -> list[dict]:
        return await self._client.list_children(folder_id)

    async def search(self, query: str, max_results: int = 10) -> list[ConnectorItem]:
        logger.debug("sharepoint.connector.search: query={!r} max_results={}", query, max_results)
        items = await self._client.search_drive(query, max_results)
        logger.debug("sharepoint.connector.search: {} item(s) from Graph", len(items))
        return [
            ConnectorItem(
                id=item.get("id", ""),
                title=item.get("name", ""),
                url=browser_url(item.get("webUrl", "")),
                snippet=(item.get("file") or {}).get("mimeType", ""),
            )
            for item in items
        ]

    async def search_in_folders(
        self, query: str, folder_urls: list[str], max_results: int = 20,
    ) -> list[ConnectorItem]:
        """Live, index-backed search scoped to one or more picked folders —
        used instead of dumping every filename when the picked scope is a
        whole folder (potentially hundreds of files)."""
        logger.debug(
            "sharepoint.connector.search_in_folders: query={!r} folders={} max_results={}",
            query, folder_urls, max_results,
        )
        items = await self._client.search_scoped(query, folder_urls, max_results)
        logger.debug("sharepoint.connector.search_in_folders: {} item(s) from Graph", len(items))
        return [
            ConnectorItem(
                id=item.get("id", ""),
                title=item.get("name", ""),
                url=browser_url(item.get("webUrl", "")),
                snippet=item.get("summary", ""),
            )
            for item in items
        ]

    async def fetch(self, item_id: str) -> str:
        """Text content of an item, prefixed with a citation header (file
        name + URL) so callers can always attribute an answer back to its
        source without having to remember the id -> name mapping from an
        earlier ``search()`` call.

        Cached by ``(item_id, lastModifiedDateTime)`` — the metadata call
        (cheap) always happens to detect edits; the expensive download+parse
        only runs when the file actually changed since it was last cached.
        """
        metadata = await self._client.get_item_metadata(item_id)
        name = metadata.get("name", "")
        url = browser_url(metadata.get("webUrl", ""))
        last_modified = metadata.get("lastModifiedDateTime", "")
        # Label provenance explicitly. Extracted PDFs often contain their
        # original public webpage URL; an unlabeled URL here lets the model
        # confuse that embedded URL with the connected SharePoint source.
        header = f"SOURCE TITLE: {name}" + (f"\nSOURCE URL: {url}" if url else "") + "\n\n"

        cached = await cache.get(SOURCE, item_id)
        if cached is not None and cached.last_modified == last_modified:
            logger.debug(
                "sharepoint.connector.fetch: item_id={!r} name={!r} cache HIT", item_id, name
            )
            return header + cached.content

        logger.debug(
            "sharepoint.connector.fetch: item_id={!r} name={!r} cache MISS, downloading",
            item_id,
            name,
        )
        content = await self._client.fetch_item_bytes(item_id)
        text = extract_text(name, content)
        await cache.put(SOURCE, item_id, name, text, last_modified)
        logger.debug(
            "sharepoint.connector.fetch: item_id={!r} downloaded {} bytes -> {} chars extracted",
            item_id,
            len(content),
            len(text),
        )
        return header + text
