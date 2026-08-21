"""Google Custom Search JSON API provider."""

from __future__ import annotations

import logging
import os

from ai.tools.search.base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)


class GoogleSearchProvider(SearchProvider):
    """Web search via Google Custom Search JSON API (requires API key + CX)."""

    ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str = "", cx: str = "") -> None:
        self._api_key = api_key or os.environ.get("GOOGLE_SEARCH_API_KEY", "")
        self._cx = cx or os.environ.get("GOOGLE_SEARCH_CX", "")

    @property
    def name(self) -> str:
        return "google"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        *,
        date_restrict: str = "",
    ) -> list[SearchResult]:
        if not self._api_key:
            raise RuntimeError("GOOGLE_SEARCH_API_KEY not set")
        if not self._cx:
            raise RuntimeError("GOOGLE_SEARCH_CX not set")

        import httpx

        # API caps num at 10 per request.
        params = {
            "key": self._api_key,
            "cx": self._cx,
            "q": query,
            "num": min(max_results, 10),
        }
        if date_restrict:
            params["dateRestrict"] = date_restrict
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self.ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("items", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            ))
        return results
