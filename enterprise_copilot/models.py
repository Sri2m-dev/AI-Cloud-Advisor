from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from data_fabric.foundation import TenantContext


@dataclass(frozen=True, slots=True)
class CopilotRequest:
    tenant_context: TenantContext
    prompt: str
    persona: str
    session_id: str
    provider: str = "mock"


@dataclass(frozen=True, slots=True)
class CopilotCitation:
    citation_id: str
    source_type: str
    source_reference: str
    label: str
    confidence: float | None
    freshness: str


@dataclass(frozen=True, slots=True)
class CopilotEvidence:
    facts: tuple[Mapping[str, Any], ...] = ()
    derived: tuple[Mapping[str, Any], ...] = ()
    citations: tuple[CopilotCitation, ...] = ()


@dataclass(frozen=True, slots=True)
class CopilotContext:
    intent: str
    entities: tuple[Mapping[str, Any], ...]
    evidence: CopilotEvidence
    unknowns: tuple[str, ...]
    policy_version: str


@dataclass(frozen=True, slots=True)
class CopilotResponse:
    response_id: str
    answer: str
    intent: str
    grounded_context: CopilotContext | None
    citations: tuple[CopilotCitation, ...]
    enterprise_confidence: float | None
    model_confidence: float | None
    policy_decisions: tuple[str, ...]
    provider: str
    blocked: bool
    unsupported: bool
    metrics: Mapping[str, Any]
    generated_at: datetime

    @staticmethod
    def identifier():
        return str(uuid4())

    @staticmethod
    def now():
        return datetime.now(timezone.utc)


@dataclass(slots=True)
class CopilotSession:
    session_id: str
    tenant_id: str
    persona: str
    messages: list[Mapping[str, Any]] = field(default_factory=list)

    def append(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        del self.messages[:-10]
