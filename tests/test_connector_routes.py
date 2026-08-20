from backend.api.routes import connectors
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


def test_canonical_connector_routes_live_in_backend_package() -> None:
    assert backend_teams.put_teams.__module__ == "backend.api.routes.connectors.teams"
    assert (
        backend_sharepoint.put_sharepoint.__module__
        == "backend.api.routes.connectors.sharepoint"
    )
    assert backend_jira.put_jira.__module__ == "backend.api.routes.connectors.jira"
