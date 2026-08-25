"""Governed monetary measure qualification and currency binding."""

from __future__ import annotations

from universal_evidence.capability.fingerprint import fingerprint
from universal_evidence.capability.models import (
    AuthorizedOperation,
    CapabilityState,
    CoverageState,
    EvidenceCoverage,
    GovernedMeasure,
    ReasonCode,
)
from universal_evidence.capability.policy import CapabilityPolicy, CoveragePolicy
from universal_evidence.normalization import NormalizationRun, NormalizationStatus


def _row_key(record) -> tuple[object, ...]:
    reference = record.row_reference
    return (
        record.source_id,
        record.file_id,
        record.sheet_id,
        reference.row_numbers,
        reference.row_range,
        reference.lineage_expression,
    )


def qualify_measures(
    runs: tuple[NormalizationRun, ...],
    coverage: tuple[EvidenceCoverage, ...],
    coverage_policy: CoveragePolicy,
    capability_policy: CapabilityPolicy,
) -> tuple[GovernedMeasure, ...]:
    by_concept = {item.semantic_concept_id: item for item in coverage}
    records = tuple(record for run in runs for record in run.records)
    currency_coverage = by_concept.get("financial.currency")
    valid_statuses = {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}
    currency_by_row = {
        _row_key(record): record.normalized_value
        for record in records
        if record.semantic_concept_id == "financial.currency"
        and record.normalization_status in valid_statuses
    }
    results = []
    for concept in sorted(capability_policy.monetary_measure_concepts):
        value_coverage = by_concept.get(concept)
        if value_coverage is None:
            continue
        value_records = tuple(
            record
            for record in records
            if record.semantic_concept_id == concept
            and record.normalization_status in valid_statuses
        )
        bound_values = tuple(
            currency_by_row[_row_key(record)]
            for record in value_records
            if _row_key(record) in currency_by_row
        )
        binding_ratio = len(bound_values) / len(value_records) if value_records else 0.0
        currencies = tuple(sorted({str(value) for value in bound_values}))
        reasons = []
        measure_usable = (
            value_coverage.coverage_state is CoverageState.EVIDENCED
            and value_coverage.validity_ratio >= coverage_policy.minimum_measure_validity_ratio
        )
        if measure_usable:
            reasons.append(ReasonCode.MEASURE_ELIGIBLE)
        else:
            reasons.append(ReasonCode.BELOW_VALIDITY_THRESHOLD)
        currency_evidenced = (
            currency_coverage is not None
            and currency_coverage.coverage_state is CoverageState.EVIDENCED
        )
        if not currency_evidenced:
            if (
                currency_coverage is not None
                and currency_coverage.observed_records > 0
                and binding_ratio < coverage_policy.minimum_row_binding_ratio
            ):
                reasons.append(ReasonCode.ROW_BINDING_INCOMPLETE)
            else:
                reasons.append(ReasonCode.UNIT_NOT_EVIDENCED)
            aggregation = CapabilityState.BLOCKED
        elif binding_ratio < coverage_policy.minimum_row_binding_ratio:
            reasons.append(ReasonCode.ROW_BINDING_INCOMPLETE)
            aggregation = CapabilityState.BLOCKED
        elif len(currencies) > 1:
            reasons.append(ReasonCode.MIXED_CURRENCY)
            aggregation = CapabilityState.BLOCKED
        elif len(currencies) == 1 and measure_usable:
            reasons.append(ReasonCode.SINGLE_CURRENCY_EVIDENCED)
            aggregation = CapabilityState.SUPPORTED
        else:
            aggregation = CapabilityState.BLOCKED
        state = CapabilityState.SUPPORTED if measure_usable else CapabilityState.BLOCKED
        provenance = value_coverage.provenance
        identity = fingerprint(
            value_coverage.scope.key,
            concept,
            value_coverage.fingerprint,
            currency_coverage.fingerprint if currency_coverage else None,
            currencies,
            binding_ratio,
            coverage_policy.version,
            capability_policy.version,
            state,
            aggregation,
        )
        results.append(
            GovernedMeasure(
                "measure-" + identity[:24],
                concept,
                value_coverage.scope,
                value_coverage.coverage_id,
                currency_coverage.coverage_id if currency_evidenced else None,
                "financial.currency" if currency_evidenced else None,
                currencies,
                binding_ratio,
                state,
                aggregation,
                (AuthorizedOperation.SUM,) if aggregation is CapabilityState.SUPPORTED else (),
                tuple(reasons),
                capability_policy.version,
                provenance,
                identity,
            )
        )
    return tuple(results)
