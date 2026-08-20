"""Compatibility facade for canonical research report synthesis."""

from ai.research.orchestration.report.synthesis import (
    build_coverage_table_with_citations,
    build_sources_list,
    build_url_citation_map,
    build_writer_finalize_message,
)

__all__ = [
    "build_coverage_table_with_citations",
    "build_sources_list",
    "build_url_citation_map",
    "build_writer_finalize_message",
]
