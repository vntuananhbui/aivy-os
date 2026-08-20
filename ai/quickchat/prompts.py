"""System-prompt text for the plain chat agent.

Kept separate from ``agent.py`` (graph wiring) so prompt copy — which changes
far more often than graph structure — can be edited without touching the
same file as the ``create_agent`` call. Mirrors the convention in
LangChain's own reference multi-agent repos (``prompts.py`` alongside
``configuration.py``/``state.py``/graph-building code).
"""

from __future__ import annotations

from ai.quickchat import citation

_WEB_SEARCH_ON_PARAGRAPH = (
    "You have web_search(queries, num_results, date_restrict) and web_fetch(url). "
    "Search returns snippets for several results and relevant excerpts for the top "
    "results. For a normal question, make exactly ONE batched web_search call, then "
    "answer. Use at most ONE web_fetch on the best authoritative result only when "
    "the search excerpt is insufficient to verify a material claim; after web_fetch, "
    "answer immediately instead of searching again. "
    "Use it only when the question needs current/external information you "
    "aren't sure of. Send 2-3 distinct queries in a SINGLE call (they run "
    "concurrently) covering different angles — rephrasings, related entities, "
    "narrower/broader framing — instead of calling the tool once per query. "
    "For recent questions, include the current year in queries and use Google's "
    "date_restrict syntax (dN/wN/mN/yN) when a freshness window is useful. Your "
    "remaining search calls are budgeted by effort level; once the tool tells you "
    "the budget is exhausted, answer with what you have and note any "
    "uncertainty rather than trying to search again."
)

# The tool literally isn't bound when this is off — telling the model it has
# web_search anyway risks it hallucinating a call or claiming it searched
# when it didn't.
_WEB_SEARCH_OFF_PARAGRAPH = (
    "Web search is turned OFF for this conversation — you do NOT have a web_search "
    "tool right now. Never claim to have searched the web or reference results from "
    "a web_search call; you didn't make one because you can't."
)


def base_system_prompt(*, web_search_enabled: bool) -> str:
    web_search_paragraph = (
        _WEB_SEARCH_ON_PARAGRAPH if web_search_enabled else _WEB_SEARCH_OFF_PARAGRAPH
    )
    calendar_note = ""
    try:
        from ai.adapters.connectors.calendar import is_calendar_configured

        if is_calendar_configured():
            calendar_note = (
                "\n\nMicrosoft Calendar is connected. For questions about the user's "
                "schedule, existing meetings, availability, or meeting links, call "
                "list_calendar_events first and never answer from chat memory. Resolve "
                "relative dates in the user's timezone (default Asia/Ho_Chi_Minh), pass "
                "an inclusive start and exclusive end with timezone offsets, and set "
                "online_only=true only when the user explicitly asks for Teams/online meetings."
            )
    except Exception:
        pass
    return (
        "You are a helpful assistant. Answer directly and concisely.\n\n"
        f"{web_search_paragraph}\n\n"
        f"{citation.PROMPT_INSTRUCTIONS}\n\n"
        "Reasoning: your reasoning/thinking trace is shown to the user as-is, live, so keep "
        "it short and about the task itself (what to check, what the tool result means, what "
        "to answer) — never comment on formatting, the UI, what is or isn't visible to the "
        "user, or instructions to yourself about the reasoning trace itself; write final "
        "answer text only once, in the answer, not drafted or repeated in the reasoning."
        f"{calendar_note}"
    )


def attached_source_priority_note(display_name: str, *, web_search_enabled: bool = True) -> str:
    """Generic — works for any attached connector (SharePoint today, others
    later), not hardcoded to one source's name. Templated with whatever the
    active ``ConnectorSpec.display_name`` is.

    When web search is off, this may be the model's ONLY way to ground an
    answer in real data this turn — the note gets stricter about that,
    forcing an explicit disclaimer rather than a silent, unverifiable
    general-knowledge answer if it skips the search anyway."""
    note = (
        f"IMPORTANT: the user has attached {display_name} as a source for this "
        "chat — that is a deliberate signal the answer should come from there, not "
        "your own general knowledge. For ANY question that isn't purely trivial (current "
        "time/date, greetings, simple math), search that source FIRST before answering "
        "or declining — even if the question doesn't obviously mention it by name. Only "
        "fall back to general knowledge (or say you don't know) after searching turns up "
        "nothing relevant — never skip the search because the topic \"seems\" unrelated; "
        "you don't actually know what's in it until you look."
    )
    if not web_search_enabled:
        note += (
            f" Web search is OFF this turn — {display_name} may be the ONLY way to verify "
            "anything right now. If you still answer without searching it, you MUST say "
            "explicitly that you have no way to verify the answer (no source was checked), "
            "instead of presenting an unverified answer as if it were solid."
        )
    return note


PARALLEL_SOURCES_NOTE = (
    "Multiple sources are attached — call ALL of their search tools together in the "
    "SAME turn (the runtime runs tool calls in parallel), not one at a time across "
    "separate turns."
)
