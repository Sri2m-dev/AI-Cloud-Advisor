from core.identity.confidence import MATCH_WEIGHTS, confidence_from_signals, resolution_status_for_score
from core.identity.identity_match import (
    IdentityMatchCandidate,
    IdentityMatchSignal,
    IdentityResolutionDecision,
    IdentityResolutionStatus,
    SourceIdentity,
    normalize_identity_text,
    source_identities_for_entity,
)
from core.identity.match_rules import identity_match_signals

IdentityMatchDecision = IdentityResolutionDecision
IdentityMatchStatus = IdentityResolutionStatus

__all__ = [
    "MATCH_WEIGHTS",
    "IdentityMatchCandidate",
    "IdentityMatchDecision",
    "IdentityMatchSignal",
    "IdentityMatchStatus",
    "IdentityResolutionDecision",
    "IdentityResolutionStatus",
    "SourceIdentity",
    "confidence_from_signals",
    "identity_match_signals",
    "normalize_identity_text",
    "resolution_status_for_score",
    "source_identities_for_entity",
]

