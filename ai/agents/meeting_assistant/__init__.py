"""Meeting assistant agent — placeholder for now.

Registered in ``quickchat/commands/catalog.py`` so an admin can bind a
``/command`` (Settings -> Commands, TUI or web) to ``AGENT_TYPE`` and reach
it from quickchat. ``build_agent`` currently always answers with a fixed
stub message via ``GenericFakeChatModel`` — no real LLM call, no tools —
just enough to prove the dispatch wiring end to end. Replace ``_run`` /
``_PLACEHOLDER_TEXT`` (and add real tools via ``get_tools``) once the actual
meeting-assistant logic is ready; the streaming/dispatch plumbing in
``quickchat/session.py`` needs no changes for that swap.
"""

from __future__ import annotations

AGENT_TYPE = "meeting_assistant"
DESCRIPTION = "Meeting assistant (placeholder — always returns a stub reply for now)."

_PLACEHOLDER_TEXT = "Đây là call tới meeting assistant, để tạm vậy đã"


def get_tools() -> list:
    return []


def build_agent(*, checkpointer=None, thinking: bool = True, effort: str = "medium"):
    """Fixed-reply stub agent, wired through the real ``create_agent`` path
    (not a hand-rolled graph) so it streams exactly like every other
    quickchat/command agent — ``langgraph_node == "model"`` message tokens,
    same checkpointer semantics — with zero special-casing needed downstream.
    ``thinking``/``effort`` are accepted (dispatcher passes them uniformly to
    every command agent) but unused by this stub.

    ``itertools.cycle`` (not ``iter([...])``) matters here: quickchat caches
    this graph and reuses it across calls (``ChatSession._command_graph_for``)
    — a one-shot iterator would raise ``StopIteration`` on the second turn.
    """
    from itertools import cycle

    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    model = GenericFakeChatModel(messages=cycle([_PLACEHOLDER_TEXT]))
    return create_agent(
        model=model,
        tools=get_tools(),
        system_prompt="You are a placeholder meeting assistant.",
        checkpointer=checkpointer,
    )
