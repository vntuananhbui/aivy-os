"""SearchProvider protocol — pluggable search backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from searchos.util.base_model import CamelModel


class SearchResult(CamelModel):
    """Unified search result from any provider."""

    title: str = ""
    url: str = ""
    snippet: str = ""
    content: str = ""  # full page content if available
    score: float = 0.0


class SearchProvider(ABC):
    """Abstract base for web search providers."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        *,
        date_restrict: str = "",
    ) -> list[SearchResult]:
        """Search for results.

        ``date_restrict`` uses Google Custom Search's ``dN``/``wN``/``mN``/
        ``yN`` syntax. Providers without an equivalent freshness filter may
        ignore it; callers should still include dates in the query itself.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
