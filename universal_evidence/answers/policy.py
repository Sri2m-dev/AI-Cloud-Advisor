"""Versioned PUE-009 deterministic composition policy."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnswerCompositionPolicy:
    version: str = "pue-answer-composition-policy-1"
    composer_version: str = "pue-deterministic-answer-composer-1"
    maximum_displayed_groups: int = 10
    include_provenance_summary: bool = True
    maximum_answer_length: int = 4000

    def __post_init__(self) -> None:
        if self.maximum_displayed_groups <= 0:
            raise ValueError("maximum displayed groups must be positive")
        if self.maximum_answer_length <= 0:
            raise ValueError("maximum answer length must be positive")
