from __future__ import annotations

from services.platform.formatting import escape_markdown_currency


class NarrativeService:
    """Shared sentence composition helpers for executive narratives."""

    @staticmethod
    def join_sentences(sentences: list[str]) -> str:
        cleaned = [str(sentence).strip() for sentence in sentences if str(sentence or "").strip()]
        return escape_markdown_currency(" ".join(cleaned))

    @staticmethod
    def ai_interpretation(*, subject: str, strengths: str, next_step: str | None = None) -> str:
        sentences = [f"{subject} is supported by {strengths}."]
        if next_step:
            sentences.append(next_step)
        return NarrativeService.join_sentences(sentences)
