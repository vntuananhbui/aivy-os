"""Cache cleanup after access revocation — the removal function only.

Deciding *when* to check access and *what* is still accessible is a BE job
(e.g. a periodic task that re-lists the user's picked files/folders via Graph
and notes which ids came back vs. 403'd) — this module only knows how to
remove, not how or when to check.
"""

from __future__ import annotations

from backend.infrastructure.connectors import cache
from backend.infrastructure.connectors.sharepoint.connector import SOURCE


async def purge_revoked(currently_accessible_ids: list[str]) -> int:
    """Remove cached SharePoint content for any item NOT in the given
    still-accessible id set. Returns the number of cache rows removed."""
    cached_ids = await cache.list_cached_ids(SOURCE)
    accessible = set(currently_accessible_ids)
    stale = [item_id for item_id in cached_ids if item_id not in accessible]
    return await cache.purge(SOURCE, stale)
