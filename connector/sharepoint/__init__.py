"""SharePoint connector — delegated (pasted-token) Microsoft Graph auth."""

from connector.sharepoint import token_store
from connector.sharepoint.connector import SharePointConnector


def get_sharepoint_tools() -> list:
    """Compatibility import; AI tool definitions live outside connector/."""
    from ai.adapters.connectors.sharepoint import get_sharepoint_tools as get_tools

    return get_tools()

__all__ = ["SharePointConnector", "get_sharepoint_tools", "token_store"]
