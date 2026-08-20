"""Sensor layer (paper §3.2) — post-tool observation + signal surface.

Plugins implement ``base.Sensor`` and return control signals (``force_stop`` /
``hint`` / writer-trigger). The engine that runs them (per-step / checkpoint)
is wired alongside the orchestrator runtime.
"""

from ai.research.orchestration.middleware.sensor.base import Sensor
from ai.research.orchestration.middleware.sensor.budget import BudgetState
from ai.research.orchestration.middleware.sensor.coverage_stall_sensor import CoverageStallSensor
from ai.research.orchestration.middleware.sensor.dispatch_round_sensor import DispatchRoundSensor
from ai.research.orchestration.middleware.sensor.loop_sensor import LoopSensorImpl
from ai.research.orchestration.middleware.sensor.writer_trigger_sensor import (
    WriterTriggerSensor,
    WriterTriggerSignal,
)

__all__ = [
    "BudgetState",
    "Sensor",
    "CoverageStallSensor",
    "DispatchRoundSensor",
    "LoopSensorImpl",
    "WriterTriggerSensor",
    "WriterTriggerSignal",
]
