"""Coverage assessment over governed PUE-004 records only."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from universal_evidence.capability.fingerprint import fingerprint
from universal_evidence.capability.models import (
    CapabilityProvenance,
    CapabilityScope,
    CoverageState,
    EvidenceCoverage,
    ReasonCode,
)
from universal_evidence.capability.policy import CoveragePolicy
from universal_evidence.normalization import (
    NormalizationRun,
    NormalizationStatus,
)
from universal_evidence.normalization.fingerprints import canonical_value


def scope_from_runs(runs: tuple[NormalizationRun, ...]) -> CapabilityScope:
    if not runs or not any(run.records for run in runs):
        raise ValueError("governed normalized evidence is required")
    records = tuple(record for run in runs for record in run.records)
    first = records[0]
    scope = CapabilityScope(
        first.analysis_id, first.prospect_id, first.organization_id, first.tenant_id
    )
    if any(
        (record.analysis_id, record.prospect_id, record.organization_id, record.tenant_id)
        != scope.key
        for record in records
    ):
        raise PermissionError("normalization runs contain conflicting evidence scope")
    return scope


def provenance_for(runs: tuple[NormalizationRun, ...], records: tuple[Any, ...]):
    return CapabilityProvenance(
        tuple(sorted({run.normalization_run_id for run in runs})),
        tuple(record.normalized_field_id for record in records),
        tuple(record.fingerprint for record in records),
        tuple(sorted({record.mapping_decision_id for record in records})),
        tuple(sorted({(record.source_id, record.file_id, record.sheet_id) for record in records})),
    )


def assess_coverage(
    runs: tuple[NormalizationRun, ...], policy: CoveragePolicy
) -> tuple[EvidenceCoverage, ...]:
    scope = scope_from_runs(runs)
    grouped: dict[str, list[Any]] = defaultdict(list)
    run_ids: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        for record in run.records:
            grouped[record.semantic_concept_id].append(record)
            run_ids[record.semantic_concept_id].add(run.normalization_run_id)
    results = []
    for concept_id in sorted(grouped):
        records = tuple(grouped[concept_id])
        observed = len(records)
        valid_statuses = {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}
        valid = sum(record.normalization_status in valid_statuses for record in records)
        nulls = sum(
            record.normalization_status is NormalizationStatus.SKIPPED for record in records
        )
        invalid = sum(
            record.normalization_status is NormalizationStatus.INVALID for record in records
        )
        partial = sum(
            record.normalization_status is NormalizationStatus.PARTIAL for record in records
        )
        unsupported = sum(
            record.normalization_status is NormalizationStatus.UNSUPPORTED for record in records
        )
        coverage_ratio = valid / observed if observed else 0.0
        attempted = observed - nulls
        validity_ratio = valid / attempted if attempted else 0.0
        invalid_ratio = invalid / observed if observed else 0.0
        reasons = [ReasonCode.GOVERNED_EVIDENCE_PRESENT]
        if (
            coverage_ratio >= policy.minimum_coverage_ratio
            and validity_ratio >= policy.minimum_validity_ratio
            and invalid_ratio <= policy.maximum_invalid_ratio
        ):
            state = CoverageState.EVIDENCED
        elif valid:
            state = CoverageState.PARTIAL
            if coverage_ratio < policy.minimum_coverage_ratio:
                reasons.append(ReasonCode.BELOW_COVERAGE_THRESHOLD)
            if validity_ratio < policy.minimum_validity_ratio:
                reasons.append(ReasonCode.BELOW_VALIDITY_THRESHOLD)
            if invalid_ratio > policy.maximum_invalid_ratio:
                reasons.append(ReasonCode.INVALID_RATIO_EXCEEDED)
        else:
            state = CoverageState.OBSERVED
            reasons.append(ReasonCode.BELOW_VALIDITY_THRESHOLD)
        distinct = len(
            {
                fingerprint(canonical_value(record.normalized_value))
                for record in records
                if record.normalization_status in valid_statuses
            }
        )
        provenance = provenance_for(runs, records)
        coverage_fingerprint = fingerprint(
            scope.key,
            concept_id,
            tuple(record.fingerprint for record in records),
            policy.version,
            state,
            tuple(reasons),
        )
        results.append(
            EvidenceCoverage(
                "coverage-" + coverage_fingerprint[:24],
                concept_id,
                scope,
                observed,
                valid,
                valid,
                nulls,
                invalid,
                partial,
                unsupported,
                coverage_ratio,
                validity_ratio,
                distinct,
                tuple(sorted({record.mapping_decision_id for record in records})),
                tuple(sorted(run_ids[concept_id])),
                provenance,
                state,
                tuple(reasons),
                policy.version,
                coverage_fingerprint,
            )
        )
    monetary_present = any(
        item.semantic_concept_id.startswith("financial.cost") for item in results
    )
    if monetary_present and "financial.currency" not in grouped:
        empty_provenance = CapabilityProvenance((), (), (), (), ())
        empty_fingerprint = fingerprint(
            scope.key,
            "financial.currency",
            policy.version,
            CoverageState.NOT_EVIDENCED,
            ReasonCode.NO_GOVERNED_EVIDENCE,
        )
        results.append(
            EvidenceCoverage(
                "coverage-" + empty_fingerprint[:24],
                "financial.currency",
                scope,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0.0,
                0.0,
                None,
                (),
                (),
                empty_provenance,
                CoverageState.NOT_EVIDENCED,
                (ReasonCode.NO_GOVERNED_EVIDENCE,),
                policy.version,
                empty_fingerprint,
            )
        )
    return tuple(sorted(results, key=lambda item: item.semantic_concept_id))
