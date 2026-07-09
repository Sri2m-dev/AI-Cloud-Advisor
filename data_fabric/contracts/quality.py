"""Data quality contract for canonical enterprise entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from data_fabric.contracts._validation import validate_score


@dataclass(slots=True)
class EntityQuality:
    """Quality dimensions used to explain trust in enterprise data."""

    completeness: float = 1.0
    freshness: float = 1.0
    accuracy: float = 1.0
    consistency: float = 1.0
    validity: float = 1.0
    trust_score: float = 1.0
    owner: str | None = None
    last_verified_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.completeness = validate_score(self.completeness, "completeness")
        self.freshness = validate_score(self.freshness, "freshness")
        self.accuracy = validate_score(self.accuracy, "accuracy")
        self.consistency = validate_score(self.consistency, "consistency")
        self.validity = validate_score(self.validity, "validity")
        self.trust_score = validate_score(self.trust_score, "trust_score")
