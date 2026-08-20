"""LangChain tools for SharePoint; retrieval logic lives in the backend."""

from __future__ import annotations

from langchain_core.tools import tool
from loguru import logger

from backend.bootstrap.connectors import sharepoint_access_service


@tool
async def sharepoint_search(query: str) -> str:
    """Search connected SharePoint/OneDrive files.

    Returns numbered file ids, names and URLs. Pass a returned id to
    ``sharepoint_read``. Use an empty string or ``*`` to list selected files.

    Args:
        query: Search query, or an empty string/``*`` to list selected files.
    """
    logger.info("sharepoint_search called: query={!r}", query)
    result = await sharepoint_access_service.search(query)
    if not result.get("success"):
        logger.warning("sharepoint_search: {}", result.get("error"))
        return f"Error: {result.get('error')}"

    items = result["results"]
    total_picked = result.get("total_picked")
    if not items:
        hint = (
            f" — {total_picked} files are picked but none matched by name or content; "
            "try a different query or narrower keywords."
            if total_picked
            else ""
        )
        return f"No SharePoint results for: {query}{hint}"
    scoped = result.get("scoped_to_picked")
    header = (
        f"SharePoint search (scoped to picked files): {query} ({len(items)} results)\n"
        if scoped
        else f"SharePoint search: {query} ({len(items)} results)\n"
    )
    if total_picked and len(items) < total_picked and query.strip().lower() in ("", "*", "all"):
        header += (
            f"(showing {len(items)} of {total_picked} picked files — "
            "narrow the query to find a specific one)\n"
        )
    lines = [header]
    for index, item in enumerate(items):
        label = f"[{index}] {item['name']} (id={item['id']})"
        if item.get("path"):
            label += f" — {item['path']}"
        lines.append(label)
        if item.get("url"):
            lines.append(f"    {item['url']}")
    return "\n".join(lines)


@tool
async def sharepoint_read(item_id: str, offset: int = 0) -> str:
    """Read a SharePoint/OneDrive file by a Graph drive-item id.

    Use an id returned by ``sharepoint_search``. The content includes labeled
    SOURCE TITLE and SOURCE URL fields for citations. For a long file, follow
    the returned continuation offset.

    Args:
        item_id: Drive item id returned by ``sharepoint_search``.
        offset: Zero-based character offset, defaulting to the file start.
    """
    logger.info("sharepoint_read called: item_id={!r} offset={}", item_id, offset)
    result = await sharepoint_access_service.read(item_id, offset=offset)
    if not result.get("success"):
        logger.warning("sharepoint_read: {}", result.get("error"))
        return f"Error: {result.get('error')}"
    content = result["content"]
    next_offset = result.get("next_offset")
    if next_offset is not None:
        content += (
            f"\n\n[... {result['total_chars'] - next_offset} more chars available — "
            f"call sharepoint_read(item_id={item_id!r}, offset={next_offset}) to continue]"
        )
    return content


def get_sharepoint_tools() -> list:
    return [sharepoint_search, sharepoint_read]


__all__ = ["get_sharepoint_tools", "sharepoint_read", "sharepoint_search"]
