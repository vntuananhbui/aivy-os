"""Vietnamese stock price access skill (FireAnt.vn), search-based.

No browser-automation binary dependency (the old ``openclaw`` script this
replaced required one). Same two-step flow openclaw used — search first,
then read the page — built entirely on infra already shared by quickchat and
the deep-research orchestrator:

1. ``tools.search`` — search "<symbol> cổ phiếu fireant" via whatever
   provider is configured (``SF_SEARCH_PROVIDER``), take the first
   fireant.vn hit (falls back to the predictable ticker URL if search
   somehow returns none).
2. ``tools.backend.base.BrowserService`` — fetch that URL via the configured
   browser backend (``SF_BROWSER_BACKEND``, default ``jina`` — renders JS,
   needed since FireAnt's price widget is client-rendered) and regex the
   price/volume/market-cap out of the returned markdown.

Validated manually against DPM/VCB/FPT/BID (see
``scripts/test_search_stock.py``, kept as a standalone repro/debug entry
point independent of the SkillContext plumbing here).
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

_PRICE_RE = re.compile(r"(\d[\d,]*\.\d+)\s*[\r\n]+\s*([+-][\d.,]+)\s*/\s*([+-]?[\d.,]+)\s*%")
_VOLUME_RE = re.compile(r"(?:KLGD|Khối lượng)[^\d]{0,20}([\d.,]+)")
_CAP_RE = re.compile(r"Vốn hóa[^\d]{0,10}([\d.,]+\s*(?:tỷ|nghìn tỷ|triệu tỷ))")
_NAME_RE = re.compile(r"^#\s*(.+?)\s*\(([A-Z]{2,5})\)", re.MULTILINE)

_MAX_SYMBOLS_PER_CALL = 5


async def _find_fireant_url(symbol: str) -> str:
    from tools.search import build_search_provider

    provider = build_search_provider("")
    query = f"{symbol} cổ phiếu fireant"
    try:
        results = await provider.search(query, max_results=5)
    except Exception as exc:
        logger.warning("aivy_search_stock: search failed for {}: {}", symbol, exc)
        results = []
    for r in results:
        if r.url and "fireant.vn" in r.url:
            return r.url
    # Search backends are flaky/rate-limited; FireAnt's ticker URL is
    # predictable, so fall back to it rather than failing outright.
    return f"https://fireant.vn/ma-chung-khoan/{symbol}"


async def _fetch_one(symbol: str) -> dict[str, Any]:
    from tools.backend.base import BrowserService

    symbol = symbol.strip().upper()
    if not symbol:
        return {"symbol": symbol, "success": False, "error": "Empty symbol"}

    url = await _find_fireant_url(symbol)
    svc = BrowserService.get()
    try:
        result = await svc.fetch(url, query=f"{symbol} stock price")
    except Exception as exc:
        logger.warning("aivy_search_stock: fetch failed for {} ({}): {}", symbol, url, exc)
        return {"symbol": symbol, "success": False, "error": str(exc), "url": url}

    if not result.ok:
        return {
            "symbol": symbol, "success": False,
            "error": result.error or f"fetch status={result.status}", "url": url,
        }

    text = result.markdown or result.html
    data: dict[str, Any] = {"symbol": symbol, "success": False, "url": url}

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
        data["error"] = "Could not parse price from FireAnt page (layout may have changed or symbol not found)"

    logger.info("aivy_search_stock: {} -> success={} price={}", symbol, data["success"], data.get("current_price"))
    return data


def _format(data: dict[str, Any]) -> str:
    symbol = data["symbol"]
    if not data.get("success"):
        return f"❌ {symbol}: {data.get('error', 'unknown error')}"

    lines = [f"📊 {symbol}" + (f" — {data['company_name']}" if data.get("company_name") else "")]
    change = data.get("change_amount", "")
    percent = data.get("change_percent", "")
    direction = ""
    try:
        direction = "▲" if float(percent.replace(",", "")) >= 0 else "▼"
    except (TypeError, ValueError, AttributeError):
        pass
    lines.append(f"Price: {data['current_price']} (nghìn VND) {direction} {change} ({percent}%)".strip())
    if data.get("volume"):
        lines.append(f"Volume: {data['volume']}")
    if data.get("market_cap"):
        lines.append(f"Market cap: {data['market_cap']}")
    lines.append(f"Source: {data['url']}")
    return "\n".join(lines)


async def check_stock(symbols: list[str]) -> dict[str, Any]:
    symbols = symbols[:_MAX_SYMBOLS_PER_CALL]
    results = [await _fetch_one(s) for s in symbols]
    return {
        "success": any(r.get("success") for r in results),
        "results": results,
        "formatted": "\n\n".join(_format(r) for r in results),
    }


async def execute(params: dict[str, Any], ctx: Any = None) -> dict[str, Any]:
    """Entry point per the shared access-skill contract.

    Parameters:
        function: "check_stock" (required)
        symbols: list[str] | str — one or more HOSE/HNX/UPCOM ticker symbols
            (comma/space-separated if passed as a string), max 5 per call
    """
    function = params.get("function", "check_stock")
    if function != "check_stock":
        return {"success": False, "error": f"Unknown function: {function}", "valid_functions": ["check_stock"]}

    raw_symbols = params.get("symbols") or params.get("symbol") or ""
    if isinstance(raw_symbols, str):
        symbols = [s for s in re.split(r"[,\s]+", raw_symbols.strip()) if s]
    else:
        symbols = [str(s) for s in raw_symbols]

    if not symbols:
        return {"success": False, "error": "Missing required parameter: symbols"}

    return await check_stock(symbols)
