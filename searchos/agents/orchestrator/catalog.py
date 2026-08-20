"""Compatibility facade for :mod:`ai.research.agents.orchestrator.catalog`."""

from ai.research.agents.orchestrator.catalog import (
    AGENT_CATALOG,
    AgentSpec,
    _is_agent_enabled,
    generate_agent_catalog_text,
    get_agent_spec,
)

__all__ = ["AGENT_CATALOG", "AgentSpec", "generate_agent_catalog_text", "get_agent_spec"]
