"""Context layer (paper §3.1) — per-agent context management: prompt assembly,
SOCM snapshot injection, compression/trim, skill injection. Read-only on SOCM.

``ControlMiddleware`` is the single seam; it wraps ``LayeredContextMiddleware``
or ``DynamicTrimMiddleware`` as its inner compressor.
"""

from ai.research.orchestration.middleware.context.control_middleware import ControlMiddleware
from ai.research.orchestration.middleware.context.dynamic_trim import DynamicTrimMiddleware
from ai.research.orchestration.middleware.context.layered_context import (
    LayeredContextMiddleware,
    SearchEpisodeMiddleware,
)

__all__ = [
    "ControlMiddleware",
    "DynamicTrimMiddleware",
    "LayeredContextMiddleware",
    "SearchEpisodeMiddleware",
]
