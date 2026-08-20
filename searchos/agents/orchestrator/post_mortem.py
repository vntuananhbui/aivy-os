"""Compatibility facade for :mod:`ai.research.agents.orchestrator.post_mortem`."""

from ai.research.agents.orchestrator.post_mortem import (
    build_failure_memory_prompt,
    compress_sub_agent_trace,
    run_post_mortem,
    short_existing_failure_memory_summary,
    validate_advice,
)

__all__ = [
    "build_failure_memory_prompt",
    "compress_sub_agent_trace",
    "run_post_mortem",
    "short_existing_failure_memory_summary",
    "validate_advice",
]
