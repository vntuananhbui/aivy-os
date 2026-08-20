"""Compatibility facade for canonical research sensors."""

from ai.research.orchestration.middleware.sensor import (
    BudgetState,
    CoverageStallSensor,
    DispatchRoundSensor,
    LoopSensorImpl,
    Sensor,
    WriterTriggerSensor,
    WriterTriggerSignal,
)

__all__ = [
    "BudgetState", "CoverageStallSensor", "DispatchRoundSensor", "LoopSensorImpl",
    "Sensor", "WriterTriggerSensor", "WriterTriggerSignal",
]
