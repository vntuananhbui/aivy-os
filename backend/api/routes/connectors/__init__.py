"""Public connector router assembled from provider-specific adapters."""

from fastapi import APIRouter

from backend.api.routes.connectors import jira, sharepoint, teams

router = APIRouter(prefix="/api/connectors")
router.include_router(sharepoint.router)
router.include_router(teams.router)
router.include_router(jira.router)

__all__ = ["jira", "router", "sharepoint", "teams"]
