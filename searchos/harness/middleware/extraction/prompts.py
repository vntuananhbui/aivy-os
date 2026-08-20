"""Compatibility facade for canonical extraction prompts."""

from ai.research.orchestration.middleware.extraction.prompts import (
    build_coverage_aware_row_prompt,
    build_discover_row_prompt,
    build_fill_row_prompt,
)

__all__ = ["build_coverage_aware_row_prompt", "build_discover_row_prompt", "build_fill_row_prompt"]
