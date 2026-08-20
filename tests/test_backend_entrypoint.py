from backend.api import main as backend_main


def _route_contract(app) -> set[tuple[str, str]]:
    return {
        (path, method.upper())
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def test_app_factory_preserves_route_contract() -> None:
    fresh_app = backend_main.create_app()

    assert _route_contract(fresh_app) == _route_contract(backend_main.app)
    assert ("/api/health", "GET") in _route_contract(fresh_app)
    assert ("/api/connectors/teams", "DELETE") in _route_contract(fresh_app)
    assert ("/api/connectors/teams", "GET") in _route_contract(fresh_app)
    assert ("/api/connectors/teams", "PUT") in _route_contract(fresh_app)
