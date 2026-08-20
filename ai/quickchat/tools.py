"""Toolset for the plain chat agent.

Deliberately its own lean ``web_search`` instead of reusing the deep-research
harness's search()/open()/find() trio (searchos/tools/simple_browser/tools.py):
that trio is built for multi-wave research and forces a separate LLM
round-trip per open() call. Chat just needs one fast answer, so one tool call
fans out several queries + their top-result page fetches concurrently and
returns everything in one shot — the model is expected to send 2-3 distinct
queries per call instead of looping single-query calls.

The number of *calls* (not queries per call) is capped per thread by the
effort level, so a low-effort chat can't spiral into the same many-round-trip
loop this tool was built to avoid.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import re
import time
from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from types import ModuleType

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_SNIPPET_CHARS = 500
_PAGE_CHARS = 3000
_FETCH_CHARS = 12000
_AUTO_FETCH_RESULTS = 2
_AUTO_FETCH_TIMEOUT_S = 10.0
_MAX_QUERIES_PER_CALL = 3
_LOG_PREVIEW_WORDS = 100

# One batched search is enough for normal chat. Higher effort gets one retry,
# but medium must not silently turn into a research-agent loop.
EFFORT_SEARCH_CALL_CAP: dict[str, int] = {"low": 1, "medium": 1, "high": 2, "max": 2}
EFFORT_FETCH_CALL_CAP: dict[str, int] = {"low": 1, "medium": 1, "high": 2, "max": 2}

# Keyed by thread_id — reset implicitly since threads are short-lived and the
# process restarts periodically; not persisted, so a server restart clears it.
_call_counts: dict[str, int] = defaultdict(int)
_fetch_counts: dict[str, int] = defaultdict(int)


def reset_web_tool_budget(thread_id: str) -> None:
    """Reset web tool counters at the start of one user turn."""
    _call_counts.pop(thread_id, None)
    _fetch_counts.pop(thread_id, None)


@tool
def get_current_time() -> str:
    """Return the current UTC date and time (ISO 8601)."""
    return datetime.now(UTC).isoformat()


@lru_cache(maxsize=1)
def _aivy_search_stock_executor() -> ModuleType:
    """Load the aivy_search_stock skill's executor.py by path (not a dotted
    import — ``skills/`` is plain skill content, not a Python package)."""
    path = (
        Path(__file__).resolve().parent.parent
        / "skills" / "global" / "access" / "aivy_search_stock" / "executor.py"
    )
    spec = importlib.util.spec_from_file_location("aivy_search_stock_executor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tool
async def aivy_search_stock(symbols: str) -> str:
    """Look up current market data for Vietnamese stocks from FireAnt.vn.

    The result includes a "Source: <url>" line per symbol — wrap each price
    you report in a <cite url="..." title="...">quote</cite> tag, same as any
    other tool result (see citing-sources instructions).

    Args:
        symbols (str): One or more ticker symbols, space/comma-separated.
            For example, "VCB" or "VCB FPT BID". Maximum 5 per call.
    """
    executor = _aivy_search_stock_executor()
    result = await executor.execute({"function": "check_stock", "symbols": symbols})
    if not result.get("success"):
        errors = "; ".join(
            r.get("error", "unknown error")
            for r in result.get("results", [])
            if not r.get("success")
        )
        return f"Error: {errors or 'no data found'}"
    return result["formatted"]


def _relevant_page_excerpt(text: str, query: str, limit: int = _PAGE_CHARS) -> str:
    """Select query-relevant chunks instead of blindly returning the page head."""
    clean = text.strip().replace("\r\n", "\n")
    if len(clean) <= limit:
        return clean

    terms = {term.casefold() for term in re.findall(r"\w+", query) if len(term) > 2}
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", clean) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > 1200:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    if not chunks:
        return clean[:limit]

    ranked = sorted(
        enumerate(chunks),
        key=lambda item: (
            -sum(item[1].casefold().count(term) for term in terms),
            item[0],
        ),
    )
    selected: list[tuple[int, str]] = []
    used = 0
    for index, chunk in ranked:
        remaining = limit - used
        if remaining <= 0:
            break
        selected.append((index, chunk[:remaining]))
        used += min(len(chunk), remaining) + 2
    return "\n\n".join(chunk for _, chunk in sorted(selected))[:limit]


async def _search_and_fetch_one(
    provider,
    query: str,
    num_results: int,
    date_restrict: str,
) -> str:
    from tools.backend.base import BrowserService

    search_started = time.monotonic()
    results = await provider.search(
        query,
        num_results,
        date_restrict=date_restrict,
    )
    search_elapsed = time.monotonic() - search_started
    if not results:
        return f"\n## Query: {query}\nNo results."

    # Google returns useful snippets for all results. Fetch only the first few
    # pages automatically; fetching 8 results for each of 3 queries meant up to
    # 24 concurrent Jina requests and made the whole tool wait for the slowest
    # page. The model can use web_fetch for any other promising result.
    urls = [r.url for r in results if r.url][:_AUTO_FETCH_RESULTS]
    fetch_started = time.monotonic()
    pages = (
        await BrowserService.get().fetch_many(
            urls,
            query=query,
            timeout=_AUTO_FETCH_TIMEOUT_S,
        )
        if urls
        else []
    )
    fetch_elapsed = time.monotonic() - fetch_started
    pages_by_result_url = dict(zip(urls, pages, strict=True))

    blocks = [f"\n## Query: {query}"]
    for rank, result in enumerate(results, start=1):
        blocks.append(f"\n[{rank}] {result.title or '(untitled)'}")
        blocks.append(f"URL: {result.url}")
        snippet = (result.snippet or "").replace("\n", " ").strip()
        if snippet:
            blocks.append(f"Snippet: {snippet[:_SNIPPET_CHARS]}")
        page = pages_by_result_url.get(result.url)
        content = result.content or (page.markdown if page is not None and page.ok else "")
        if content:
            blocks.append(f"Content: {_relevant_page_excerpt(content, query)}")
    rendered = "\n".join(blocks)
    preview = " ".join(rendered.split()[:_LOG_PREVIEW_WORDS])
    logger.info(
        "web_search %r -> %d results | provider=%.2fs fetch_top_%d=%.2fs | preview: %s",
        query,
        len(results),
        search_elapsed,
        len(urls),
        fetch_elapsed,
        preview,
    )
    return rendered


def make_web_fetch_tool(effort: str = "medium"):
    """Build a deep-page fetch tool with a small per-turn call budget."""
    call_cap = EFFORT_FETCH_CALL_CAP.get(effort, 1)

    @tool
    async def web_fetch(url: str, config: RunnableConfig) -> str:
        """Read one promising web page more deeply after web_search.

        Use this only when a search excerpt is insufficient to verify a material
        claim. Prefer the single most authoritative URL. After this call, answer
        the user instead of continuing to browse unless the tool reports failure.

        Args:
            url (str): Exact HTTP(S) URL returned by web_search.
        """
        from tools.backend.base import BrowserService

        thread_id = (config.get("configurable") or {}).get("thread_id", "")
        _fetch_counts[thread_id] += 1
        if _fetch_counts[thread_id] > call_cap:
            return (
                f"Error: deep-fetch budget exhausted ({call_cap} call(s) this turn). "
                "Answer now using the evidence already gathered."
            )

        page = await BrowserService.get().fetch(url)
        if not page.ok or not page.markdown:
            return f"Error: unable to fetch {url}: {page.error or page.status}"
        return (
            f"# {page.title or 'Web page'}\nSource URL: {page.url or url}\n\n"
            f"{page.markdown[:_FETCH_CHARS]}"
        )

    return web_fetch


def make_web_search_tool(effort: str = "medium"):
    """Build a ``web_search`` tool with a per-thread call budget for ``effort``."""
    call_cap = EFFORT_SEARCH_CALL_CAP.get(effort, 2)

    @tool
    async def web_search(
        queries: list[str],
        config: RunnableConfig,
        num_results: int = 8,
        date_restrict: str = "",
    ) -> str:
        """Search with several concurrent queries and return fetched excerpts.

        Send 2-3 distinct queries in one call that cover different angles of
        the question (rephrasings, related entities, a narrower/broader
        framing) instead of calling this tool once per query. Only call it
        again if these combined results genuinely don't answer the question —
        your remaining calls on this budget are limited.

        Args:
            queries (list[str]): 1-3 distinct search queries. Include an explicit
                year/date in each query for latest/current questions.
            num_results (int): results per query (1-10, default 8).
            date_restrict (str): optional Google freshness window: dN, wN, mN,
                or yN (for example d7 or m3). Leave empty unless recency matters.
        """
        from searchos.tools.simple_browser.state import get_provider, set_browser_provider
        from tools.search import build_search_provider

        thread_id = (config.get("configurable") or {}).get("thread_id", "")
        _call_counts[thread_id] += 1
        if _call_counts[thread_id] > call_cap:
            return (
                f"Error: search budget exhausted ({call_cap} call(s) for this effort "
                "level). Answer the question using the results already gathered above; "
                "state any remaining uncertainty rather than searching again."
            )

        if get_provider() is None:
            set_browser_provider(build_search_provider(""))
        provider = get_provider()
        if provider is None:
            return "Error: search provider not configured."

        clean_queries = [q.strip() for q in queries if q and q.strip()][:_MAX_QUERIES_PER_CALL]
        if not clean_queries:
            return "Error: queries must contain at least one non-empty query"
        num_results = max(1, min(int(num_results), 10))
        date_restrict = date_restrict.strip().lower()
        if date_restrict and not re.fullmatch(r"[dwmy][1-9]\d*", date_restrict):
            return (
                "Error: date_restrict must be empty or use dN/wN/mN/yN syntax "
                "(for example d7 or m3)"
            )

        sections = await asyncio.gather(
            *(
                _search_and_fetch_one(provider, q, num_results, date_restrict)
                for q in clean_queries
            )
        )
        noun = "query" if len(clean_queries) == 1 else "queries"
        return f"# Search results ({len(clean_queries)} {noun})" + "".join(sections)

    return web_search


def get_chat_tools(
    effort: str = "medium", *, sources: list | None = None, web_search_enabled: bool = True,
) -> list:
    """``sources`` — active connectors from ``ai.quickchat.sources.active_sources()``.
    Pass it explicitly when the caller already computed it (e.g.
    ``build_chat_agent``, which also needs it for the prompt) to avoid a
    second lookup; omitted, it's computed here.

    ``web_search_enabled`` — the composer's "Google Search" source chip,
    per-request rather than a connected/disconnected server state like the
    ``sources`` above (there's nothing to "connect" — the API key is already
    configured; this is just a per-turn on/off)."""
    from ai.quickchat.sources import active_sources, tools_for_sources

    tools = [get_current_time, aivy_search_stock]
    from ai.adapters.connectors.calendar import (
        is_calendar_configured,
        list_calendar_events,
    )

    if is_calendar_configured():
        tools.append(list_calendar_events)
    if web_search_enabled:
        tools.extend((make_web_search_tool(effort), make_web_fetch_tool(effort)))
    if sources is None:
        sources = active_sources()
    tools.extend(tools_for_sources(sources))
    return tools
