"""Compatibility facade for connector routes migrated to ``backend``."""

from backend.api.routes.connectors import router
from backend.api.routes.connectors.jira import (  # noqa: F401
    JiraConnect,
    JiraSelectionUpdate,
    _JIRA_AUTHORIZE_URL,
    _JIRA_OAUTH_SCOPES,
    _JIRA_RESOURCES_URL,
    _JIRA_TOKEN_URL,
    _OAUTH_STATE_TTL,
    _oauth_message_page,
    delete_jira,
    get_jira,
    jira_oauth_callback,
    jira_oauth_start,
    put_jira,
    put_jira_selection,
)
from backend.api.routes.connectors.sharepoint import (  # noqa: F401
    SharePointConnect,
    SharePointItemIn,
    SharePointSelectionUpdate,
    browse_sharepoint,
    delete_sharepoint,
    get_sharepoint,
    put_sharepoint,
    put_sharepoint_selection,
)
from backend.api.routes.connectors.teams import (  # noqa: F401
    TeamsConnect,
    delete_teams,
    get_teams,
    put_teams,
)
