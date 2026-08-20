"""Registry of available external-source connectors.

Lets a caller (quickchat's prompt wiring today; a future settings UI)
enumerate "what sources are currently active" generically — without
hardcoding one connector's name — so a second connector doesn't require
touching every call site that currently says "sharepoint".

Deliberately minimal: just a type -> class map plus an active-sources list.
Auth flow and settings-storage shape differ enough per connector (paste-token
vs OAuth redirect, file/folder selection vs none, ...) that forcing a shared
request/response schema across connectors before a second real one exists
would be guessing at requirements nobody has yet — see
``backend/api/routes/connectors/sharepoint.py`` for why that stays sharepoint-specific for
now rather than a generic ``/api/connectors/{type}``. Register a real second
connector's routes/settings the same way sharepoint's are built, adjusting
where its actual needs diverge — not by conforming to an invented shape here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from connector.base import ConnectorBase


@dataclass(frozen=True)
class ConnectorSpec:
    type: str
    display_name: str
    connector_cls: type[ConnectorBase]
    is_active: Callable[[], bool]


_REGISTRY: dict[str, ConnectorSpec] = {}
_registered_builtins = False


def register(spec: ConnectorSpec) -> None:
    _REGISTRY[spec.type] = spec


def _ensure_builtins_registered() -> None:
    """Lazy — avoids import-time coupling between this module and every
    connector package (each connector's own ``is_active`` may itself need
    web-only deps like ``api.settings_store``, only safe to touch when
    actually called, not at import time)."""
    global _registered_builtins
    if _registered_builtins:
        return
    _registered_builtins = True

    from backend.bootstrap.connectors import connector_capability_reader
    from connector.sharepoint.connector import SharePointConnector

    register(ConnectorSpec(
        type="sharepoint",
        display_name="SharePoint/OneDrive",
        connector_cls=SharePointConnector,
        is_active=lambda: connector_capability_reader.is_connected("sharepoint"),
    ))

    from connector.jira.connector import JiraConnector

    register(ConnectorSpec(
        type="jira",
        display_name="Jira",
        connector_cls=JiraConnector,
        is_active=lambda: connector_capability_reader.is_connected("jira"),
    ))


def list_active_sources() -> list[ConnectorSpec]:
    """Every registered connector whose ``is_active()`` currently returns
    True — e.g. sharepoint once a token is connected. Empty list means no
    external source is attached right now."""
    _ensure_builtins_registered()
    return [spec for spec in _REGISTRY.values() if spec.is_active()]


def is_source_active(source: str) -> bool:
    """Return readiness for one registered source without importing AI tools."""
    _ensure_builtins_registered()
    spec = _REGISTRY.get(source)
    return bool(spec and spec.is_active())
