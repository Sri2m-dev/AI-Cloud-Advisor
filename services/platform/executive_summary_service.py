from __future__ import annotations

from typing import Any

from services.platform.narrative_service import NarrativeService


class ExecutiveSummaryService:
    """Reusable summary payload builder for certified pages."""

    @staticmethod
    def build(*, title: str, sentences: list[str], metrics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {
            "title": title,
            "narrative": NarrativeService.join_sentences(sentences),
            "metrics": metrics or [],
        }
