from __future__ import annotations

import unittest
from unittest.mock import patch

from ai.quickchat.tools import _relevant_page_excerpt, _search_and_fetch_one
from tools.backend.base import BrowserService, FetchResult
from tools.search.base import SearchResult
from tools.search.google import GoogleSearchProvider


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "items": [
                {"title": "Result", "link": "https://example.com", "snippet": "Summary"}
            ]
        }


class _FakeHttpClient:
    last_params: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def get(self, endpoint: str, *, params: dict):
        self.__class__.last_params = params
        return _FakeResponse()


class _FakeProvider:
    date_restrict = ""

    async def search(self, query, max_results, *, date_restrict=""):
        self.date_restrict = date_restrict
        return [
            SearchResult(
                title="Redirected page",
                url="https://example.com/old",
                snippet="Short snippet",
            )
        ]


class _FakeBrowserService:
    query = ""
    timeout = 0.0

    async def fetch_many(self, urls, *, query="", timeout=20.0):
        self.query = query
        self.timeout = timeout
        return [
            FetchResult(
                url="https://example.com/new",
                markdown="Header\n\nThe target fact is 42 and is supported here.",
            )
        ]


class QuickchatWebSearchTests(unittest.IsolatedAsyncioTestCase):
    def test_excerpt_prefers_query_relevant_content(self) -> None:
        page = ("Unrelated introduction.\n\n" * 200) + "Revenue target reached 42 million."
        excerpt = _relevant_page_excerpt(page, "revenue target", limit=300)
        self.assertIn("Revenue target reached 42 million", excerpt)

    async def test_google_passes_supported_date_restrict(self) -> None:
        provider = GoogleSearchProvider(api_key="key", cx="cx")
        with patch("httpx.AsyncClient", return_value=_FakeHttpClient()):
            results = await provider.search("latest result", 8, date_restrict="d7")

        self.assertEqual(len(results), 1)
        self.assertEqual(_FakeHttpClient.last_params["num"], 8)
        self.assertEqual(_FakeHttpClient.last_params["dateRestrict"], "d7")

    async def test_redirected_fetch_is_kept_and_query_is_forwarded(self) -> None:
        provider = _FakeProvider()
        browser = _FakeBrowserService()
        previous = BrowserService._instance
        BrowserService._instance = browser
        try:
            output = await _search_and_fetch_one(provider, "target fact", 8, "m1")
        finally:
            BrowserService._instance = previous

        self.assertEqual(provider.date_restrict, "m1")
        self.assertEqual(browser.query, "target fact")
        self.assertEqual(browser.timeout, 10.0)
        self.assertIn("The target fact is 42", output)


if __name__ == "__main__":
    unittest.main()
