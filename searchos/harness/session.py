"""Compatibility facade for :mod:`ai.research.orchestration.session`."""

from ai.research.orchestration.session import (
    SearchResult,
    SearchSession,
    close_browser_service,
    wait_for_all_evolutions,
)

__all__ = [
    "SearchResult",
    "SearchSession",
    "close_browser_service",
    "wait_for_all_evolutions",
]
