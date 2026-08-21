"""Compatibility facade for Calendar AI tools relocated to ``ai.adapters``."""

from ai.adapters.connectors.calendar import (
    is_calendar_configured,
    list_calendar_events,
)


def is_configured() -> bool:
    return is_calendar_configured()


__all__ = ["is_configured", "list_calendar_events"]
