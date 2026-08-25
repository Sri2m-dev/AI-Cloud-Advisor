"""PUE-C5A execution-shape metadata; performs no aggregation."""

from __future__ import annotations

from universal_evidence.capability.fingerprint import fingerprint
from universal_evidence.capability.models import (
    AlignmentStatus,
    AuthorizedOperation,
    CapabilityState,
    EvidenceAlignment,
    ExecutionAuthorization,
    ReasonCode,
    RecordBasisType,
    RecordCountBasis,
)
from universal_evidence.capability.policy import CapabilityPolicy
from universal_evidence.normalization import NormalizationStatus

VALID = {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}


def _row_key(record) -> tuple[object, ...]:
    reference = record.row_reference
    return (
        record.analysis_id,
        record.prospect_id,
        record.organization_id,
        record.tenant_id,
        record.source_id,
        record.file_id,
        record.sheet_id,
        reference.row_numbers,
        reference.row_range,
        reference.lineage_expression,
    )


def _row_fingerprints(records) -> tuple[str, ...]:
    return tuple(sorted(fingerprint("SOURCE_ROW", _row_key(record)) for record in records))


def build_record_basis(runs, scope, policy) -> RecordCountBasis:
    records = tuple(record for run in runs for record in run.records)
    row_fingerprints = tuple(sorted(set(_row_fingerprints(records))))
    row_set_fingerprint = fingerprint("SOURCE_ROW_SET", row_fingerprints)
    identity = fingerprint(
        scope.key,
        RecordBasisType.SOURCE_ROW,
        row_fingerprints,
        tuple(sorted(run.normalization_run_id for run in runs)),
        policy.execution_authorization_version,
    )
    return RecordCountBasis(
        "record-basis-" + identity[:24],
        scope,
        RecordBasisType.SOURCE_ROW,
        "analysis+prospect+organization+tenant+source+file+sheet+row",
        len(row_fingerprints),
        row_fingerprints[: policy.max_materialized_row_references],
        row_set_fingerprint,
        "distinct SOURCE_ROW provenance within certified normalization runs",
        tuple(sorted(run.normalization_run_id for run in runs)),
        policy.execution_authorization_version,
        identity,
    )


def build_alignments(runs, scope, measures, dimensions, policy):
    records = tuple(record for run in runs for record in run.records)
    results = []
    for measure in measures:
        measure_records = tuple(
            record
            for record in records
            if record.semantic_concept_id == measure.semantic_concept_id
            and record.normalization_status in VALID
        )
        measure_rows = set(_row_fingerprints(measure_records))
        for dimension in dimensions:
            if dimension.state is not CapabilityState.SUPPORTED:
                continue
            related_records = tuple(
                record
                for record in records
                if record.semantic_concept_id == dimension.semantic_concept_id
                and record.normalization_status in VALID
            )
            related_rows = set(_row_fingerprints(related_records))
            aligned = tuple(sorted(measure_rows & related_rows))
            aligned_set_fingerprint = fingerprint("ALIGNED_SOURCE_ROW_SET", aligned)
            if measure_rows and measure_rows == related_rows:
                status = AlignmentStatus.ALIGNED
                reasons = (ReasonCode.CAPABILITY_PREREQUISITES_MET,)
            elif aligned:
                status = AlignmentStatus.PARTIALLY_ALIGNED
                reasons = (ReasonCode.ROW_BINDING_INCOMPLETE,)
            else:
                status = AlignmentStatus.NOT_ALIGNED
                reasons = (ReasonCode.ROW_BINDING_INCOMPLETE,)
            is_time = any(
                fragment in dimension.semantic_concept_id
                for fragment in policy.time_concept_fragments
            )
            identity = fingerprint(
                scope.key,
                measure.measure_id,
                dimension.dimension_id,
                measure_rows,
                related_rows,
                aligned,
                status,
                policy.execution_authorization_version,
            )
            results.append(
                EvidenceAlignment(
                    "alignment-" + identity[:24],
                    scope,
                    measure.measure_id,
                    None if is_time else dimension.dimension_id,
                    dimension.dimension_id if is_time else None,
                    measure.currency_coverage_id,
                    "SOURCE_ROW",
                    tuple(sorted(measure.provenance.normalization_run_ids)),
                    tuple(sorted(dimension.provenance.normalization_run_ids)),
                    len(measure_rows),
                    len(related_rows),
                    len(aligned),
                    aligned[: policy.max_materialized_row_references],
                    aligned_set_fingerprint,
                    "intersection of measure and related SOURCE_ROW provenance",
                    status,
                    reasons,
                    policy.execution_authorization_version,
                    identity,
                )
            )
    return tuple(results)


def build_authorizations(
    assessment_id,
    assessment_fingerprint,
    scope,
    capabilities,
    measures,
    dimensions,
    alignments,
    record_basis,
    policy: CapabilityPolicy,
):
    by_name = {item.capability_name: item for item in capabilities}
    results = []

    def add(
        capability_name,
        operation,
        *,
        measure=None,
        dimension=None,
        alignment=None,
        time=False,
        record_count=False,
    ):
        capability = by_name.get(capability_name)
        if capability is None or capability.state is not CapabilityState.SUPPORTED:
            return
        identity = fingerprint(
            scope.key,
            assessment_fingerprint,
            capability.capability_id,
            operation,
            measure.measure_id if measure else None,
            dimension.dimension_id if dimension else None,
            alignment.alignment_id if alignment else None,
            record_basis.record_basis_id if record_count else None,
            policy.execution_authorization_version,
        )
        results.append(
            ExecutionAuthorization(
                "authorization-" + identity[:24],
                assessment_id,
                capability.capability_id,
                scope,
                (operation,),
                measure.measure_id if measure else None,
                (dimension.dimension_id,) if dimension and not time else (),
                dimension.dimension_id if dimension and time else None,
                policy.allowed_time_buckets if time else (),
                (
                    "ROW_LEVEL_GOVERNED_CURRENCY"
                    if capability_name == "CURRENCY_GROUPED_TOTAL"
                    else "ROW_LEVEL_SINGLE_CURRENCY"
                )
                if measure
                else None,
                "COMPATIBLE_GOVERNED_UNIT" if measure else None,
                alignment.alignment_id if alignment else None,
                record_basis.record_basis_id if record_count else None,
                tuple(
                    sorted(
                        set(capability.provenance.normalization_run_ids)
                        | (set(alignment.measure_normalization_run_ids) if alignment else set())
                        | (set(alignment.related_normalization_run_ids) if alignment else set())
                    )
                ),
                policy.execution_authorization_version,
                assessment_fingerprint,
                identity,
            )
        )

    add("COUNT_EVIDENCE_RECORDS", AuthorizedOperation.COUNT, record_count=True)
    for measure in measures:
        if (
            measure.aggregation_eligibility is CapabilityState.SUPPORTED
            and AuthorizedOperation.SUM in measure.permitted_aggregation_functions
        ):
            add("MONETARY_TOTAL", AuthorizedOperation.SUM, measure=measure)
        for alignment in alignments:
            if alignment.measure_id != measure.measure_id:
                continue
            dimension_id = alignment.time_dimension_id or alignment.dimension_id
            dimension = next(
                (item for item in dimensions if item.dimension_id == dimension_id), None
            )
            if dimension is None or alignment.alignment_status is not AlignmentStatus.ALIGNED:
                continue
            if (
                alignment.time_dimension_id
                and measure.aggregation_eligibility is CapabilityState.SUPPORTED
            ):
                add(
                    "MONETARY_TREND",
                    AuthorizedOperation.TIME_BUCKETED_SUM,
                    measure=measure,
                    dimension=dimension,
                    alignment=alignment,
                    time=True,
                )
            elif (
                alignment.dimension_id
                and measure.aggregation_eligibility is CapabilityState.SUPPORTED
                and dimension.semantic_concept_id != "financial.currency"
            ):
                add(
                    "MONETARY_TOTAL_BY_DIMENSION",
                    AuthorizedOperation.GROUPED_SUM,
                    measure=measure,
                    dimension=dimension,
                    alignment=alignment,
                )
            if (
                dimension.semantic_concept_id == "financial.currency"
                and len(measure.detected_currencies) > 1
            ):
                add(
                    "CURRENCY_GROUPED_TOTAL",
                    AuthorizedOperation.GROUPED_SUM,
                    measure=measure,
                    dimension=dimension,
                    alignment=alignment,
                )
    return tuple(results)
