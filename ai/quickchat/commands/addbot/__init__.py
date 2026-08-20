"""Example command agent for quickchat's ``/addbot`` slash command.

Template for adding a new command: copy this folder, change ``AGENT_TYPE``/
``DESCRIPTION``/``agent.md``/``get_tools()``, then register the new module in
``ai/quickchat/commands/catalog.py``. An admin then binds a command name (e.g.
``"addbot"``) to this ``AGENT_TYPE`` from the TUI's Commands section
(``searchos/tui/config_modal.py``) — see ``ai/quickchat/commands/__init__.py``.
"""

from __future__ import annotations

from pathlib import Path

AGENT_TYPE = "addbot"
DESCRIPTION = "Example/template command agent — replace with real tools and agent.md."

_AGENT_MD_PATH = Path(__file__).resolve().parent / "agent.md"


def get_tools() -> list:
    from ai.quickchat.tools import get_current_time

    return [get_current_time]


def _system_prompt() -> str:
    from ai.common.toolset_render import render_toolset

    template = _AGENT_MD_PATH.read_text()
    return template.replace("{toolset}", render_toolset(get_tools()))


def build_agent(*, checkpointer=None, thinking: bool = True, effort: str = "medium"):
    """Build this command's agent graph.

    ``checkpointer`` is passed in by the dispatcher (``ai/quickchat/session.py``)
    — normally the SAME checkpointer/thread the main chat agent uses, so the
    command's exchange lands in the ongoing conversation history instead of
    a separate memory.
    """
    from langchain.agents import create_agent

    from ai.quickchat.agent import CHAT_EFFORT_TO_REASONING
    from ai.quickchat.middleware import build_middleware_stack
    from searchos.config.models import get_model_for, resolve_profile

    reasoning_effort = None
    if resolve_profile("chat").enable_thinking:
        reasoning_effort = CHAT_EFFORT_TO_REASONING.get(effort, "low") if thinking else "none"

    return create_agent(
        model=get_model_for("chat", reasoning_effort=reasoning_effort),
        tools=get_tools(),
        system_prompt=_system_prompt(),
        checkpointer=checkpointer,
        middleware=build_middleware_stack(role="chat"),
    )
