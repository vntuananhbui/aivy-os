"""Compatibility facade for :mod:`ai.research.agents.runtime`."""

from ai.research.agents.runtime import (
    _agent_graph_var,
    _budget_exhausted_var,
    _check_call_count_var,
    _completed_var,
    _conversation_logger_var,
    _ctx,
    _granularity_hints_var,
    _pop_granularity_hints,
    _post_mortem_count_var,
    _post_mortem_tasks_var,
    _scheduler,
    _scheduler_var,
    _session_search_count_var,
    _skill_registry_var,
    _sub_agent_counter_var,
    _task_pool_var,
    create_search_agent_graph,
    set_orchestrator_context,
)

__all__ = ["create_search_agent_graph", "set_orchestrator_context"]
