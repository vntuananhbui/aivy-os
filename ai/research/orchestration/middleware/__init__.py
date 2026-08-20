"""Three-layer deep-research middleware stack: Context → Sensor → Extraction."""

from ai.research.orchestration.middleware.sensor.base import Sensor
from ai.research.orchestration.middleware.sensor.budget import BudgetState


def build_layered_stack(
    *,
    control: list | None = None,
    sensor: list | None = None,
    extraction: list | None = None,
) -> list:
    """Flatten instantiated middleware without changing layer order."""
    return [*(control or []), *(sensor or []), *(extraction or [])]


__all__ = ["Sensor", "BudgetState", "build_layered_stack"]
