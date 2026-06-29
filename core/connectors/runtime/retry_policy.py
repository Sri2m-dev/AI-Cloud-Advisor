from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class RetryBackoffStrategy(str, Enum):
    FIXED = "Fixed"
    LINEAR = "Linear"
    EXPONENTIAL = "Exponential"


@dataclass(slots=True)
class ConnectorRetryPolicy:
    name: str = "Default Connector Retry Policy"
    id: UUID = field(default_factory=uuid4)
    max_attempts: int = 3
    initial_delay_seconds: int = 30
    backoff_strategy: str = RetryBackoffStrategy.EXPONENTIAL.value
    retry_on_statuses: tuple[str, ...] = ("Failed",)
    metadata: dict[str, Any] = field(default_factory=dict)

    def delay_for_attempt(self, attempt: int) -> int:
        if attempt <= 1:
            return 0
        if self.backoff_strategy == RetryBackoffStrategy.FIXED.value:
            return self.initial_delay_seconds
        if self.backoff_strategy == RetryBackoffStrategy.LINEAR.value:
            return self.initial_delay_seconds * (attempt - 1)
        return self.initial_delay_seconds * (2 ** (attempt - 2))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["retry_on_statuses"] = list(self.retry_on_statuses)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorRetryPolicy":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["retry_on_statuses"] = tuple(data.get("retry_on_statuses", ("Failed",)))
        return cls(**data)
