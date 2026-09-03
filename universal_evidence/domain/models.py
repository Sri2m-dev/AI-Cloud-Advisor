from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DomainClass(str, Enum):
    CLOUD_BILLING = "CLOUD_BILLING"
    SAAS_LICENSING = "SAAS_LICENSING"
    TECHNOLOGY_INVENTORY = "TECHNOLOGY_INVENTORY"
    APPLICATION_INVENTORY = "APPLICATION_INVENTORY"
    CMDB = "CMDB"
    CONTRACT = "CONTRACT"
    OWNERSHIP = "OWNERSHIP"
    FINANCE_COST_CENTER = "FINANCE_COST_CENTER"
    MONITORING = "MONITORING"
    SECURITY = "SECURITY"
    UNKNOWN = "UNKNOWN"


class ProviderClass(str, Enum):
    AWS = "AWS"
    AZURE = "AZURE"
    GCP = "GCP"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class DomainConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class DomainGovernanceState(str, Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DomainSignal:
    signal_type: str
    detail: str
    contribution: float
    references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DomainAssessment:
    domain: DomainClass
    provider: ProviderClass
    score: float
    confidence: DomainConfidence
    supporting_evidence: tuple[DomainSignal, ...]
    conflicting_evidence: tuple[DomainSignal, ...]
    explanation: str
    classifier_version: str
    policy_version: str
    governance_state: DomainGovernanceState
    confirmation_required: bool
    fingerprint: str
