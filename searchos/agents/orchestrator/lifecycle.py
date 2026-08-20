"""Compatibility facade for :mod:`ai.research.agents.orchestrator.lifecycle`."""

from ai.research.agents.orchestrator.lifecycle import *  # noqa: F403
from ai.research.agents.orchestrator.lifecycle import (
    _agent_graph_var,
    _collect_sub_agent_result,
    _ctx,
    _record_skill_failure,
    _spawn_sub_agent,
    _task_redundancy_reason,
)
