"""Compatibility re-export for the migrated Teams connector routes."""

from backend.api.routes.connectors.teams import (  # noqa: F401
    TeamsConnect,
    delete_teams,
    get_teams,
    put_teams,
    router,
)
