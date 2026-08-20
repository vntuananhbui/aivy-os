from connector.teams import token_store


def is_configured() -> bool:
    from ai.adapters.connectors.calendar import is_calendar_configured

    return is_calendar_configured()


def __getattr__(name: str):
    if name == "list_calendar_events":
        from ai.adapters.connectors.calendar import list_calendar_events

        return list_calendar_events
    raise AttributeError(name)


__all__ = ["is_configured", "list_calendar_events", "token_store"]
