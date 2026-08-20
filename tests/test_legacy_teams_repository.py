import asyncio
from types import SimpleNamespace

from backend.infrastructure.connectors import legacy


def test_status_cross_checks_config_with_process_token(monkeypatch) -> None:
    repository = legacy.LegacyTeamsConnectionRepository()
    monkeypatch.setattr(
        legacy.settings_store,
        "store",
        SimpleNamespace(connectors=SimpleNamespace(teams=SimpleNamespace(connected=True))),
    )
    monkeypatch.setattr(legacy.teams_token_store, "get_token", lambda: None)

    assert asyncio.run(repository.status()) == {"connected": False}
