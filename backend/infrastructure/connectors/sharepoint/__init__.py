"""SharePoint connector — delegated (pasted-token) Microsoft Graph auth."""

from backend.infrastructure.connectors.sharepoint import token_store
from backend.infrastructure.connectors.sharepoint.connector import SharePointConnector


def get_sharepoint_tools() -> list:
    """Compatibility import; AI tool definitions live under ``ai.adapters``."""
    from ai.adapters.connectors.sharepoint import get_sharepoint_tools as get_tools

    return get_tools()

__all__ = ["SharePointConnector", "get_sharepoint_tools", "token_store"]
