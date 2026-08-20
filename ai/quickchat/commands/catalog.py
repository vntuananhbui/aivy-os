"""Fixed catalog of command agents an admin can bind a ``/command`` to.

Mirrors ``searchos/agents/orchestrator/catalog.py::AGENT_CATALOG``'s shape.
Deliberately a closed list, not a free-text dotted-path lookup: the admin UI
(``searchos/tui/config_modal.py``'s Commands section) only lets the admin
*choose* an ``agent_type`` from here — never type an arbitrary import path —
so a config edit can never cause arbitrary code execution. Adding a new
command agent is a code change (new ``ai/quickchat/commands/<name>/`` module +
one line here), same trust boundary as adding a new orchestrator sub-agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ai.agents import bot_join, meeting_assistant, teams_meeting_action
from ai.quickchat.commands import addbot


@dataclass(frozen=True)
class CommandAgentSpec:
    agent_type: str
    description: str
    build: Callable[..., Any]  # build(*, checkpointer=None, thinking=True, effort="medium") -> compiled graph


COMMAND_CATALOG: dict[str, CommandAgentSpec] = {
    bot_join.AGENT_TYPE: CommandAgentSpec(
        agent_type=bot_join.AGENT_TYPE,
        description=bot_join.DESCRIPTION,
        build=bot_join.build_agent,
    ),
    addbot.AGENT_TYPE: CommandAgentSpec(
        agent_type=addbot.AGENT_TYPE,
        description=addbot.DESCRIPTION,
        build=addbot.build_agent,
    ),
    meeting_assistant.AGENT_TYPE: CommandAgentSpec(
        agent_type=meeting_assistant.AGENT_TYPE,
        description=meeting_assistant.DESCRIPTION,
        build=meeting_assistant.build_agent,
    ),
    teams_meeting_action.AGENT_TYPE: CommandAgentSpec(
        agent_type=teams_meeting_action.AGENT_TYPE,
        description=teams_meeting_action.DESCRIPTION,
        build=teams_meeting_action.build_agent,
    ),
}


def get_command_spec(agent_type: str) -> CommandAgentSpec | None:
    return COMMAND_CATALOG.get(agent_type)
