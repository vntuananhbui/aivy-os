"""SharePoint access-skill adapter.

The backend application service owns connection state and retrieval behavior;
this module only translates the skill contract into service calls.
"""

from __future__ import annotations

from typing import Any

from backend.bootstrap.connectors import sharepoint_access_service


async def execute(params: dict[str, Any], ctx: Any = None) -> dict[str, Any]:
    function = params.get("function")
    if function == "search":
        return await sharepoint_access_service.search(params.get("query", ""))
    if function == "read":
        item_id = params.get("item_id", "")
        if not item_id:
            return {"success": False, "error": "Missing required parameter: item_id"}
        return await sharepoint_access_service.read(
            item_id,
            offset=int(params.get("offset", 0) or 0),
        )
    return {
        "success": False,
        "error": f"Unknown function: {function}",
        "valid_functions": ["search", "read"],
    }
