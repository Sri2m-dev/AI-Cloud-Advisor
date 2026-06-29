from __future__ import annotations

from core.identity.identity_match import IdentityMatchSignal, IdentityResolutionStatus


MATCH_WEIGHTS = {
    "exact_source_identity": 100,
    "external_id_match": 95,
    "hostname_match": 90,
    "ip_address_match": 90,
    "cloud_resource_id_match": 95,
    "normalized_name_match": 70,
    "owner_match": 40,
    "application_tag_match": 50,
    "environment_match": 25,
    "vendor_match": 25,
    "region_match": 20,
    "same_cloud_account": 60,
    "same_tags": 30,
}


def confidence_from_signals(signals: list[IdentityMatchSignal]) -> int:
    if not signals:
        return 0
    return min(100, max(signal.score for signal in signals) + _supporting_signal_bonus(signals))


def resolution_status_for_score(score: int) -> str:
    if score >= 90:
        return IdentityResolutionStatus.AUTO_MATCHED.value
    if score >= 70:
        return IdentityResolutionStatus.NEEDS_REVIEW.value
    return IdentityResolutionStatus.REJECTED.value


def _supporting_signal_bonus(signals: list[IdentityMatchSignal]) -> int:
    supporting = sorted((signal.score for signal in signals), reverse=True)[1:]
    return min(10, sum(max(1, score // 20) for score in supporting))

