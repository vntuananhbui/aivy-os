"""Extraction layer（paper §3.3）。

``EvidenceExtractionMiddleware`` 是 Agent 生命周期 Adapter；``EvidenceIntake``
是 Evidence Graph 与 Coverage Map 的唯一写入模块。
"""

from ai.research.orchestration.middleware.extraction.evidence_extraction import (
    EvidenceExtractionMiddleware,
)
from ai.research.orchestration.middleware.extraction.intake import EvidenceIntake

ExtractionMiddleware = EvidenceExtractionMiddleware  # plan §三 alias

__all__ = ["EvidenceExtractionMiddleware", "EvidenceIntake", "ExtractionMiddleware"]
