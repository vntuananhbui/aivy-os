"""Provider-neutral connector capability descriptors.

This module deliberately exposes no provider client or persistence type. The
current single-process composition reader is resolved lazily until capability
state is injected as part of the production persistence migration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorSpec:
    type: str
    display_name: str


_KNOWN_SOURCES = (
    ConnectorSpec(type="sharepoint", display_name="SharePoint/OneDrive"),
    ConnectorSpec(type="jira", display_name="Jira"),
)


def is_source_active(source: str) -> bool:
    from backend.bootstrap.connectors import connector_capability_reader

    return connector_capability_reader.is_connected(source)


def list_active_sources() -> list[ConnectorSpec]:
    return [source for source in _KNOWN_SOURCES if is_source_active(source.type)]


__all__ = ["ConnectorSpec", "is_source_active", "list_active_sources"]
