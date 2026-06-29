from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class CertificationSeverity(str, Enum):
    BLOCKER = "Blocker"
    WARNING = "Warning"
    INFO = "Info"


class CertificationCheckStatus(str, Enum):
    PASSED = "Passed"
    FAILED = "Failed"
    WARNING = "Warning"
    SKIPPED = "Skipped"


@dataclass(slots=True)
class ConnectorCertificationCheck:
    name: str
    status: str
    severity: str
    message: str
    id: UUID = field(default_factory=uuid4)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConnectorCertificationCheck":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        return cls(**data)
