"""Common interface for external-source connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ConnectorItem:
    """One hit from a connector search — analogous to ``SearchResult``."""

    id: str
    title: str = ""
    url: str = ""
    snippet: str = ""


@dataclass
class ConnectorStatus:
    connected: bool
    detail: str = ""


class ConnectorBase(ABC):
    """A pluggable external-source connector (SharePoint, Drive, ...)."""

    @abstractmethod
    async def connect(self) -> ConnectorStatus:
        """Validate the current config against the live service.

        Raises on hard failure; returns a ``ConnectorStatus`` describing the
        outcome otherwise.
        """

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[ConnectorItem]:
        """Search the connected source, returning addressable items."""

    @abstractmethod
    async def fetch(self, item_id: str) -> str:
        """Fetch the text content of a previously-listed item."""
