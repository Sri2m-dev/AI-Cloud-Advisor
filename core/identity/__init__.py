from core.identity.identity_resolution import (
    IdentityMatchCandidate,
    IdentityMatchSignal,
    IdentityResolutionDecision,
    IdentityResolutionStatus,
    SourceIdentity,
)
from core.identity.confidence import MATCH_WEIGHTS, confidence_from_signals, resolution_status_for_score
from core.identity.match_rules import identity_match_signals

__all__ = [
    "MATCH_WEIGHTS",
    "IdentityMatchCandidate",
    "IdentityMatchSignal",
    "IdentityResolutionDecision",
    "IdentityResolutionStatus",
    "SourceIdentity",
    "confidence_from_signals",
    "identity_match_signals",
    "resolution_status_for_score",
]
