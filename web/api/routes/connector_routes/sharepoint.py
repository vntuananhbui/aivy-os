"""Compatibility re-export for the migrated SharePoint connector routes."""

from backend.api.routes.connectors.sharepoint import (  # noqa: F401
    SharePointConnect,
    SharePointItemIn,
    SharePointSelectionUpdate,
    browse_sharepoint,
    delete_sharepoint,
    get_sharepoint,
    put_sharepoint,
    put_sharepoint_selection,
    router,
)
