"""SharePoint content access use cases, independent from the AI adapters."""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.application.connectors.repositories import SharePointConnectionRepository
from backend.application.connectors.provider_ports import (
    SharePointProvider,
    SharePointProviderFactory,
)


def _graph_error_message(exc: Exception) -> str:
    if getattr(exc, "status_code", None) == 404:
        return (
            f"{exc} — this id may be stale (the search index can lag behind recent "
            "file changes). Search SharePoint again to get a fresh id."
        )
    return str(exc)


class SharePointAccessService:
    MAX_FOLDER_SCOPE_RESULTS = 20
    MAX_PICKED_LIST_RESULTS = 20
    MAX_READ_CHARS = 8000

    def __init__(
        self,
        repository: SharePointConnectionRepository,
        connector_factory: SharePointProviderFactory,
    ) -> None:
        self._repository = repository
        self._connector_factory = connector_factory

    async def _connector(self) -> SharePointProvider | None:
        status = await self._repository.status()
        token = await self._repository.get_access_token()
        if not status or not status.get("connected") or not token:
            return None
        return self._connector_factory(token)

    async def search(self, query: str) -> dict[str, Any]:
        logger.info("sharepoint.access.search: query={!r}", query)
        connector = await self._connector()
        if connector is None:
            return {"success": False, "error": "SharePoint connector not configured or not connected."}

        picked = await self._repository.get_selection()
        files = [item for item in picked if not item.is_folder]
        folders = [item for item in picked if item.is_folder]
        query_lc = query.strip().lower()
        list_all = query_lc in ("", "*", "all")

        if folders:
            try:
                hits = await connector.search_in_folders(
                    "" if list_all else query,
                    [folder.web_url for folder in folders if folder.web_url],
                    max_results=self.MAX_FOLDER_SCOPE_RESULTS,
                )
            except Exception as exc:
                return {"success": False, "error": _graph_error_message(exc)}
            results = [
                {"id": hit.id, "name": hit.title, "url": hit.url, "snippet": hit.snippet}
                for hit in hits
            ]
            file_matches = files if list_all else [item for item in files if query_lc in item.name.lower()]
            results = [
                {"id": item.id, "name": item.name, "path": item.path}
                for item in file_matches
            ] + results
            return {"success": True, "scoped_to_picked": True, "results": results}

        if files:
            name_matches = files if list_all else [item for item in files if query_lc in item.name.lower()]
            results = [
                {"id": item.id, "name": item.name, "path": item.path}
                for item in name_matches[: self.MAX_PICKED_LIST_RESULTS]
            ]
            if not list_all and len(name_matches) < self.MAX_PICKED_LIST_RESULTS:
                try:
                    hits = await connector.search(query, max_results=self.MAX_FOLDER_SCOPE_RESULTS)
                except Exception as exc:
                    return {"success": False, "error": _graph_error_message(exc)}
                picked_ids = {item.id for item in files}
                seen_ids = {item["id"] for item in results}
                for hit in hits:
                    if hit.id in picked_ids and hit.id not in seen_ids:
                        results.append({"id": hit.id, "name": hit.title, "url": hit.url})
                        seen_ids.add(hit.id)
            return {
                "success": True,
                "scoped_to_picked": True,
                "results": results,
                "total_picked": len(files),
            }

        try:
            hits = await connector.search(query)
        except Exception as exc:
            return {"success": False, "error": _graph_error_message(exc)}
        return {
            "success": True,
            "scoped_to_picked": False,
            "results": [{"id": hit.id, "name": hit.title, "url": hit.url} for hit in hits],
        }

    async def read(self, item_id: str, offset: int = 0) -> dict[str, Any]:
        connector = await self._connector()
        if connector is None:
            return {"success": False, "error": "SharePoint connector not configured or not connected."}
        try:
            full_content = await connector.fetch(item_id)
        except Exception as exc:
            return {"success": False, "error": _graph_error_message(exc)}
        offset = max(0, offset)
        chunk = full_content[offset : offset + self.MAX_READ_CHARS]
        next_offset = offset + len(chunk)
        return {
            "success": True,
            "content": chunk,
            "total_chars": len(full_content),
            "next_offset": next_offset if next_offset < len(full_content) else None,
        }
