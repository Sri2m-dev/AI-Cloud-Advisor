"""Governed PUE contracts to bounded Stage 1/2 display models."""

from universal_evidence.activation.fingerprint import fingerprint
from universal_evidence.capability import CapabilityState, CoverageState, ReasonCode
from universal_evidence.pilot.models import (
    CapabilityViewItem,
    EvidenceViewItem,
    PilotDetails,
    PilotVisibility,
    PuePilotViewModel,
)

COVERAGE_LABELS = {
    CoverageState.EVIDENCED: "Available",
    CoverageState.PARTIAL: "Partially available",
    CoverageState.NOT_EVIDENCED: "Not evidenced",
    CoverageState.INSUFFICIENT: "Insufficient evidence",
    CoverageState.CONFLICTED: "Conflicting evidence",
    CoverageState.BLOCKED: "Governed use blocked",
    CoverageState.OBSERVED: "Observed",
}

CAPABILITY_LABELS = {
    CapabilityState.SUPPORTED: "Available",
    CapabilityState.PARTIALLY_SUPPORTED: "Partially available",
    CapabilityState.BLOCKED: "Blocked",
    CapabilityState.NOT_SUPPORTED: "Not supported",
    CapabilityState.UNKNOWN: "Unknown",
}

CONCEPT_LABELS = {
    "cloud.provider": "Cloud provider",
    "technology.service": "Technology service",
    "resource.identifier": "Resource identifier",
    "cloud.region": "Region",
    "geography.region": "Region",
    "application.name": "Application",
    "ownership.owner": "Owner",
    "organization.cost_center": "Cost center",
    "financial.cost.total": "Cost",
    "financial.cost.monthly": "Monthly cost",
    "financial.currency": "Currency",
    "contract.renewal_date": "Contract renewal",
    "contract.start_date": "Usage date",
}

BASELINE_ABSENCE = (
    ("financial.currency", "Currency"),
    ("security.risk", "Security risk"),
    ("business.criticality", "Business criticality"),
    ("service.sla", "SLA"),
)

CAPABILITY_LABEL_NAMES = {
    "DESCRIBE_AVAILABLE_EVIDENCE": "Describe available evidence",
    "COUNT_EVIDENCE_RECORDS": "Record count",
    "FILTER_BY_DIMENSION": "Filter by governed dimension",
    "TIME_RANGE_ANALYSIS": "Time-range analysis",
    "MONETARY_TREND": "Cost trend",
    "MONETARY_TOTAL": "Total cost",
    "MONETARY_TOTAL_BY_DIMENSION": "Cost by governed dimension",
    "CURRENCY_GROUPED_TOTAL": "Cost grouped by currency",
    "FX_NORMALIZED_TOTAL": "FX-normalized total",
    "RESOURCE_INVENTORY": "Resource inventory",
    "APPLICATION_INVENTORY": "Application inventory",
    "OWNER_INVENTORY": "Owner inventory",
    "REGION_INVENTORY": "Region inventory",
    "CONTRACT_INVENTORY": "Contract inventory",
}

REASON_TEXT = {
    ReasonCode.UNIT_NOT_EVIDENCED: "Currency evidence is not sufficiently governed.",
    ReasonCode.MIXED_CURRENCY: "Multiple currencies prevent a single governed total.",
    ReasonCode.BELOW_COVERAGE_THRESHOLD: "Evidence coverage is below the governed threshold.",
    ReasonCode.BELOW_VALIDITY_THRESHOLD: "Valid evidence is below the governed threshold.",
    ReasonCode.INVALID_RATIO_EXCEEDED: "Invalid evidence exceeds the governed threshold.",
    ReasonCode.REQUIRED_DIMENSION_MISSING: "A required governed dimension is not evidenced.",
    ReasonCode.REQUIRED_MEASURE_MISSING: "A required governed measure is not evidenced.",
    ReasonCode.REQUIRED_TIME_DIMENSION_MISSING: "A required governed time field is not evidenced.",
    ReasonCode.FX_NOT_SUPPORTED: "FX conversion is not supported.",
    ReasonCode.ROW_BINDING_INCOMPLETE: "The required evidence is not aligned by source row.",
    ReasonCode.NO_GOVERNED_EVIDENCE: "No governed evidence supports this capability.",
}


def evidence_items(assessment):
    items = []
    observed = set()
    for coverage in sorted(assessment.coverage, key=lambda item: item.semantic_concept_id):
        observed.add(coverage.semantic_concept_id)
        reason = _reason(coverage.reason_codes)
        items.append(
            EvidenceViewItem(
                coverage.semantic_concept_id,
                CONCEPT_LABELS.get(
                    coverage.semantic_concept_id,
                    coverage.semantic_concept_id.replace(".", " ").title(),
                ),
                coverage.coverage_state.value,
                COVERAGE_LABELS[coverage.coverage_state],
                reason,
            )
        )
    for concept_id, label in BASELINE_ABSENCE:
        if concept_id not in observed:
            items.append(
                EvidenceViewItem(
                    concept_id,
                    label,
                    CoverageState.NOT_EVIDENCED.value,
                    COVERAGE_LABELS[CoverageState.NOT_EVIDENCED],
                    "No governed evidence for this concept is present in the current analysis.",
                )
            )
    return tuple(items)


def capability_items(assessment):
    return tuple(
        CapabilityViewItem(
            capability.capability_id,
            CAPABILITY_LABEL_NAMES.get(
                capability.capability_name,
                capability.capability_name.replace("_", " ").title(),
            ),
            capability.state.value,
            CAPABILITY_LABELS[capability.state],
            _capability_reason(capability, assessment),
        )
        for capability in assessment.capabilities
    )


def _capability_reason(capability, assessment):
    if capability.capability_name.startswith("MONETARY_"):
        currency = next(
            (
                item
                for item in assessment.coverage
                if item.semantic_concept_id == "financial.currency"
            ),
            None,
        )
        if currency is None or currency.coverage_state is CoverageState.NOT_EVIDENCED:
            return REASON_TEXT[ReasonCode.UNIT_NOT_EVIDENCED]
        if currency.distinct_count is not None and currency.distinct_count > 1:
            return REASON_TEXT[ReasonCode.MIXED_CURRENCY]
    return _reason(capability.reason_codes)


def build_view_model(*, activation, shadow, visibility):
    assessment = shadow.capability_assessment
    evidence = evidence_items(assessment)
    capabilities = (
        capability_items(assessment)
        if visibility is PilotVisibility.DISCOVERY_AND_CAPABILITY
        else ()
    )
    details = PilotDetails(
        1,
        shadow.source_sheets,
        shadow.source_rows,
        len(shadow.provenance.mapping_decision_ids),
        len(shadow.normalization_runs),
    )
    identity = fingerprint(
        visibility,
        activation.fingerprint,
        shadow.fingerprint,
        evidence,
        capabilities,
        details,
    )
    return PuePilotViewModel(
        visibility,
        assessment.scope,
        "GOVERNED EVIDENCE PILOT",
        "Current prospect analysis remains authoritative during this pilot.",
        "Governed Evidence Discovery",
        evidence,
        "Analysis Capability" if capabilities else None,
        capabilities,
        details,
        None,
        activation.fingerprint,
        shadow.fingerprint,
        identity,
    )


def unavailable_view_model(*, activation, scope, shadow_fingerprint=None):
    message = (
        "Governed evidence discovery is temporarily unavailable. "
        "Your current prospect analysis is unaffected."
    )
    identity = fingerprint(
        PilotVisibility.UNAVAILABLE,
        activation.fingerprint,
        scope,
        shadow_fingerprint,
        message,
    )
    return PuePilotViewModel(
        PilotVisibility.UNAVAILABLE,
        scope,
        "GOVERNED EVIDENCE PILOT",
        "Current prospect analysis remains authoritative during this pilot.",
        "Governed Evidence Discovery",
        (),
        None,
        (),
        None,
        message,
        activation.fingerprint,
        shadow_fingerprint,
        identity,
    )


def build_upload_admission_view_model(*, activation, admission, visibility):
    primary = next(
        (item for item in admission.regions if item.region_kind == "PRIMARY_DETAIL"),
        None,
    )
    evidence = (
        tuple(
            EvidenceViewItem(
                f"source-column:{index}",
                header,
                "PENDING_GOVERNANCE",
                "Observed - not yet governed",
                "The source column was observed structurally; "
                "semantic meaning is not yet governed.",
            )
            for index, header in enumerate(primary.original_headers, start=1)
            if header
        )
        if primary
        else ()
    )
    capabilities = ()
    if visibility is PilotVisibility.DISCOVERY_AND_CAPABILITY:
        capabilities = (
            CapabilityViewItem(
                "MONETARY_TOTAL",
                "Total cost",
                "BLOCKED",
                "Blocked",
                "No governed monetary measure and currency mapping authorizes aggregation.",
            ),
            CapabilityViewItem(
                "DESCRIBE_AVAILABLE_EVIDENCE",
                "Governed evidence description",
                "UNKNOWN",
                "Pending governance",
                "Structural evidence is available; semantic mappings are not yet governed.",
            ),
        )
    details = PilotDetails(
        1,
        len(admission.profile.sheets),
        primary.detail_record_count if primary else None,
        0,
        0,
    )
    identity = fingerprint(
        visibility, activation.fingerprint, admission.fingerprint, evidence, capabilities
    )
    return PuePilotViewModel(
        visibility,
        admission.scope,
        "GOVERNED EVIDENCE PILOT - UPLOAD STRUCTURE",
        "Structural discovery is shadow-only; the legacy prospect path remains authoritative.",
        "Governed Evidence Discovery",
        evidence,
        "Analysis Capability" if capabilities else None,
        capabilities,
        details,
        None,
        activation.fingerprint,
        admission.fingerprint,
        identity,
    )


def _reason(reason_codes):
    for code in reason_codes:
        if code in REASON_TEXT:
            return REASON_TEXT[code]
    return "Governed evidence policy produced this state."
