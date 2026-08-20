"""Compatibility facade for canonical research middleware assembly."""

from ai.research.orchestration.middleware import BudgetState, Sensor, build_layered_stack

__all__ = ["Sensor", "BudgetState", "build_layered_stack"]
