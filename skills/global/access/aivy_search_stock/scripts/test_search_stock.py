#!/usr/bin/env python3
"""Standalone test for the aivy_search_stock approach — no openclaw dependency.

Same two-step flow as the old openclaw script (search Google for the FireAnt
page, then read it), but built entirely on infra already in this repo:

1. ``tools.search.build_search_provider()`` — same provider quickchat's
   web_search tool uses (Serper/Tavily/Google/RagFlow per SF_SEARCH_PROVIDER)
   — search "<symbol> cổ phiếu fireant" and take the first fireant.vn hit.
2. ``tools.backend.base.BrowserService`` — same fetch backend quickchat/deep-
   research use (per SF_BROWSER_BACKEND, default jina — renders JS) — fetch
   that URL and regex the price/volume/market-cap out of the markdown.

Run: python3 skills/global/access/aivy_search_stock/scripts/test_search_stock.py DPM VCB FPT
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root

_PRICE_RE = re.compile(r"(\d[\d,]*\.\d+)\s*[\r\n]+\s*([+-][\d.,]+)\s*/\s*([+-]?[\d.,]+)\s*%")
_VOLUME_RE = re.compile(r"(?:KLGD|Khối lượng)[^\d]{0,20}([\d.,]+)")
_CAP_RE = re.compile(r"Vốn hóa[^\d]{0,10}([\d.,]+\s*(?:tỷ|nghìn tỷ|triệu tỷ))")
_NAME_RE = re.compile(r"^#\s*(.+?)\s*\(([A-Z]{2,5})\)", re.MULTILINE)


async def find_fireant_url(symbol: str) -> str | None:
    from tools.search import build_search_provider

    provider = build_search_provider("")
    query = f"{symbol} cổ phiếu fireant"
    print(f"  [search] provider={provider.__class__.__name__} query={query!r}")
    results = await provider.search(query, max_results=5)
    for r in results:
        print(f"    - {r.url}")
    for r in results:
        if r.url and "fireant.vn" in r.url:
            return r.url
    # Fallback: FireAnt's ticker URL is predictable even if search misses it.
    return f"https://fireant.vn/ma-chung-khoan/{symbol}"


async def fetch_and_parse(symbol: str, url: str) -> dict:
    from tools.backend.base import BrowserService

    svc = BrowserService.get()
    result = await svc.fetch(url, query=f"{symbol} stock price")
    print(f"  [fetch] status={result.status} ok={result.ok} chars={len(result.markdown)}")
    if not result.ok:
        return {"symbol": symbol, "success": False, "error": result.error or f"status={result.status}", "url": url}

    text = result.markdown or result.html
    data: dict = {"symbol": symbol, "success": False, "url": url}

    name_match = _NAME_RE.search(text)
    if name_match:
        data["company_name"] = name_match.group(1).strip()

    price_match = _PRICE_RE.search(text)
    if price_match:
        data["current_price"] = price_match.group(1)
        data["change_amount"] = price_match.group(2)
        data["change_percent"] = price_match.group(3)
        data["success"] = True

    vol_match = _VOLUME_RE.search(text)
    if vol_match:
        data["volume"] = vol_match.group(1)

    cap_match = _CAP_RE.search(text)
    if cap_match:
        data["market_cap"] = cap_match.group(1)

    if not data["success"]:
        data["error"] = "price pattern not found in fetched content"
        data["raw_excerpt"] = text[:800]

    return data


async def check_one(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    print(f"\n=== {symbol} ===")
    url = await find_fireant_url(symbol)
    if not url:
        return {"symbol": symbol, "success": False, "error": "no fireant.vn URL found in search results"}
    print(f"  [url] {url}")
    return await fetch_and_parse(symbol, url)


async def main(symbols: list[str]) -> None:
    for symbol in symbols:
        data = await check_one(symbol)
        print(f"  [result] {data}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_search_stock.py <SYMBOL1> [SYMBOL2] ...")
        sys.exit(1)
    asyncio.run(main(sys.argv[1:]))
