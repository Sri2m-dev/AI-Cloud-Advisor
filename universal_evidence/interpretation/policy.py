"""Versioned PUE-008 deterministic interpretation policy."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InterpretationPolicy:
    version: str = "pue-interpretation-policy-1"
    question_version: str = "pue-natural-language-question-1"
    interpreter_name: str = "deterministic-analytical-interpreter"
    interpreter_version: str = "pue-interpreter-1"
    catalog_version: str = "pue-analytical-concept-catalog-1"
    alias_registry_version: str = "pue-analytical-aliases-1"
    pattern_registry_version: str = "pue-intent-patterns-1"
    literal_policy_version: str = "pue-typed-literals-1"
    minimum_interpretation_score: float = 0.75
    ambiguity_gap: float = 0.12
    maximum_question_length: int = 500

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_interpretation_score <= 1:
            raise ValueError("minimum interpretation score must be between zero and one")
        if not 0 <= self.ambiguity_gap <= 1:
            raise ValueError("ambiguity gap must be between zero and one")
        if self.maximum_question_length <= 0:
            raise ValueError("maximum question length must be positive")
