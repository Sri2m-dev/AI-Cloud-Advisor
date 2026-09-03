"""Explainable, governed source-domain recognition."""

from universal_evidence.domain.classifier import assess_domain
from universal_evidence.domain.models import (
    DomainAssessment,
    DomainClass,
    DomainConfidence,
    DomainGovernanceState,
    DomainSignal,
    ProviderClass,
)

__all__ = [
    "DomainAssessment",
    "DomainClass",
    "DomainConfidence",
    "DomainGovernanceState",
    "DomainSignal",
    "ProviderClass",
    "assess_domain",
]
