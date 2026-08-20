"""Compatibility facade for the relocated SharePoint AI tools.

New AI code should import :mod:`ai.adapters.connectors.sharepoint` directly.
"""

from ai.adapters.connectors.sharepoint import (
    get_sharepoint_tools,
    sharepoint_read,
    sharepoint_search,
)
from backend.bootstrap.connectors import connector_capability_reader


def is_configured() -> bool:
    """Legacy synchronous capability check used while graphs are built."""
    return connector_capability_reader.is_connected("sharepoint")


__all__ = [
    "get_sharepoint_tools",
    "is_configured",
    "sharepoint_read",
    "sharepoint_search",
]
