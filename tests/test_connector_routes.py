from api.routes import connectors
from api.routes.connector_routes import jira
from api.routes.connector_routes import sharepoint
from api.routes.connector_routes import teams
from backend.api.routes.connectors import jira as backend_jira
from backend.api.routes.connectors import sharepoint as backend_sharepoint
from backend.api.routes.connectors import teams as backend_teams
from fastapi import FastAPI


def _route_methods_by_path() -> dict[str, set[str]]:
    app = FastAPI()
    app.include_router(connectors.router)
    return {
        path: {method.upper() for method in operations}
        for path, operations in app.openapi()["paths"].items()
    }


def test_teams_routes_keep_existing_public_contract() -> None:
    routes = _route_methods_by_path()

    assert routes["/api/connectors/teams"] == {"GET", "PUT", "DELETE"}


def test_sharepoint_routes_keep_existing_public_contract() -> None:
    routes = _route_methods_by_path()

    assert routes["/api/connectors/sharepoint"] == {"GET", "PUT", "DELETE"}
    assert routes["/api/connectors/sharepoint/browse"] == {"GET"}
    assert routes["/api/connectors/sharepoint/selection"] == {"PUT"}


def test_jira_routes_keep_existing_public_contract() -> None:
    routes = _route_methods_by_path()

    assert routes["/api/connectors/jira"] == {"GET", "PUT", "DELETE"}
    assert routes["/api/connectors/jira/selection"] == {"PUT"}
    assert routes["/api/connectors/jira/oauth/start"] == {"GET"}
    assert routes["/api/connectors/jira/oauth/callback"] == {"GET"}


def test_legacy_teams_route_symbols_are_reexported() -> None:
    assert teams.router is backend_teams.router
    assert connectors.TeamsConnect is teams.TeamsConnect
    assert connectors.get_teams is teams.get_teams
    assert connectors.put_teams is teams.put_teams
    assert connectors.delete_teams is teams.delete_teams


def test_legacy_sharepoint_route_symbols_are_reexported() -> None:
    assert sharepoint.router is backend_sharepoint.router
    assert connectors.SharePointConnect is sharepoint.SharePointConnect
    assert connectors.SharePointItemIn is sharepoint.SharePointItemIn
    assert connectors.SharePointSelectionUpdate is sharepoint.SharePointSelectionUpdate
    assert connectors.get_sharepoint is sharepoint.get_sharepoint
    assert connectors.put_sharepoint is sharepoint.put_sharepoint
    assert connectors.browse_sharepoint is sharepoint.browse_sharepoint
    assert connectors.put_sharepoint_selection is sharepoint.put_sharepoint_selection
    assert connectors.delete_sharepoint is sharepoint.delete_sharepoint


def test_legacy_jira_route_symbols_are_reexported() -> None:
    assert jira.router is backend_jira.router
    assert connectors.JiraConnect is backend_jira.JiraConnect
    assert connectors.JiraSelectionUpdate is backend_jira.JiraSelectionUpdate
    assert connectors.get_jira is backend_jira.get_jira
    assert connectors.put_jira is backend_jira.put_jira
    assert connectors.put_jira_selection is backend_jira.put_jira_selection
    assert connectors.delete_jira is backend_jira.delete_jira
    assert connectors.jira_oauth_start is backend_jira.jira_oauth_start
    assert connectors.jira_oauth_callback is backend_jira.jira_oauth_callback


def test_canonical_connector_routes_live_in_backend_package() -> None:
    assert backend_teams.put_teams.__module__ == "backend.api.routes.connectors.teams"
    assert (
        backend_sharepoint.put_sharepoint.__module__
        == "backend.api.routes.connectors.sharepoint"
    )
    assert backend_jira.put_jira.__module__ == "backend.api.routes.connectors.jira"
