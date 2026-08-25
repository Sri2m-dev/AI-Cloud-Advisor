"""Governed row normalization authorized only by current PUE-003 decisions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from universal_evidence.governance import (
    EffectiveSemanticMapping,
    InMemoryMappingDecisionRepository,
    MappingDecisionState,
)
from universal_evidence.normalization.fingerprints import canonical_value, fingerprint
from universal_evidence.normalization.models import (
    AuthorizedSourceValue,
    NormalizationProvenance,
    NormalizationRun,
    NormalizationRunStatus,
    NormalizationStatus,
    NormalizedEvidenceField,
)
from universal_evidence.normalization.policy import NormalizationPolicy
from universal_evidence.normalization.registry import NormalizerRegistry
from universal_evidence.normalization.repository import InMemoryNormalizedEvidenceRepository
from universal_evidence.normalization.warnings import NormalizationWarning
from universal_evidence.semantic.concepts import DEFAULT_CONCEPT_REGISTRY

AUTHORIZED_STATES = frozenset(
    {
        MappingDecisionState.AUTO_ACCEPTED,
        MappingDecisionState.CONFIRMED,
        MappingDecisionState.OVERRIDDEN,
    }
)


class NormalizationService:
    def __init__(
        self,
        *,
        decision_repository: InMemoryMappingDecisionRepository,
        repository: InMemoryNormalizedEvidenceRepository | None = None,
        policy: NormalizationPolicy | None = None,
        registry: NormalizerRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.decision_repository = decision_repository
        self.repository = repository or InMemoryNormalizedEvidenceRepository()
        self.policy = policy or NormalizationPolicy()
        self.registry = registry or NormalizerRegistry(DEFAULT_CONCEPT_REGISTRY)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def normalize(
        self,
        mapping: EffectiveSemanticMapping,
        values: Iterable[AuthorizedSourceValue],
    ) -> NormalizationRun:
        decision = self._authorize(mapping)
        started_at = self.clock()
        version_key = tuple(str(item) for item in mapping.scope.key)
        previous_runs = self.repository.get_versions(version_key)
        previous = previous_runs[-1] if previous_runs else None
        mapping_changed = previous is not None and (
            previous.mapping_decision_id != mapping.decision_id
        )
        records = tuple(
            self._normalize_value(mapping, decision, item, mapping_changed) for item in values
        )
        completed_at = self.clock()
        invalid_count = sum(
            record.normalization_status is NormalizationStatus.INVALID for record in records
        )
        skipped_count = sum(
            record.normalization_status is NormalizationStatus.SKIPPED for record in records
        )
        normalized_count = sum(
            record.normalization_status
            in {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}
            for record in records
        )
        partial = any(
            record.normalization_status
            in {
                NormalizationStatus.INVALID,
                NormalizationStatus.PARTIAL,
                NormalizationStatus.UNSUPPORTED,
                NormalizationStatus.SKIPPED,
            }
            for record in records
        )
        status = NormalizationRunStatus.PARTIAL if partial else NormalizationRunStatus.COMPLETE
        mapping_set_fingerprint = fingerprint(
            mapping.scope.key,
            mapping.semantic_concept_id,
            mapping.decision_id,
            mapping.provenance,
        )
        run_fingerprint = fingerprint(
            mapping_set_fingerprint,
            self.policy.version,
            tuple(record.fingerprint for record in records),
        )
        run = NormalizationRun(
            "normalization-run-" + run_fingerprint[:24],
            mapping.scope.analysis_id,
            mapping_set_fingerprint,
            mapping.decision_id,
            self.policy.version,
            started_at,
            completed_at,
            status,
            records,
            len(records),
            normalized_count,
            invalid_count,
            skipped_count,
            previous.normalization_run_id if mapping_changed else None,
            run_fingerprint,
        )
        return self.repository.store_run(run, version_key)

    def _authorize(self, mapping: EffectiveSemanticMapping):
        if mapping.decision_state not in AUTHORIZED_STATES:
            raise PermissionError("mapping decision state does not authorize normalization")
        current = self.decision_repository.effective(mapping.scope)
        if current is None:
            raise PermissionError("an effective PUE-003 mapping is required")
        if current.decision_id != mapping.decision_id:
            raise PermissionError("superseded mapping cannot authorize normalization")
        if (
            current.semantic_concept_id != mapping.semantic_concept_id
            or current.decision_state != mapping.decision_state
            or current.actor != mapping.actor
            or current.provenance != mapping.provenance
        ):
            raise PermissionError("mapping does not match the effective PUE-003 decision")
        return current

    def _normalize_value(
        self,
        mapping: EffectiveSemanticMapping,
        decision: Any,
        item: AuthorizedSourceValue,
        mapping_changed: bool,
    ) -> NormalizedEvidenceField:
        self._verify_row_scope(mapping, item)
        source_value = item.source_value
        warnings: tuple[NormalizationWarning, ...] = (
            (NormalizationWarning.MAPPING_CHANGED,) if mapping_changed else ()
        )
        used_cached_formula_value = False
        if item.formula_expression is not None:
            if self.policy.allow_cached_formula_values and item.cached_formula_value is not None:
                source_value = item.cached_formula_value
                used_cached_formula_value = True
                status: NormalizationStatus | None = None
            else:
                normalized_value = None
                normalized_type = None
                status = NormalizationStatus.PARTIAL
                warnings += (NormalizationWarning.FORMULA_VALUE_UNRESOLVED,)
        elif source_value is None or (isinstance(source_value, str) and not source_value.strip()):
            normalized_value = None
            normalized_type = None
            status = NormalizationStatus.SKIPPED
            warnings += (NormalizationWarning.NULL_VALUE,)
        else:
            status = None

        normalizer = self.registry.normalizer(mapping.semantic_concept_id)
        if status is None and normalizer is None:
            normalized_value = None
            normalized_type = None
            status = NormalizationStatus.UNSUPPORTED
            warnings += (NormalizationWarning.UNSUPPORTED_VALUE_TYPE,)
        elif status is None:
            normalized_value, normalized_type, status, new_warnings = normalizer(
                source_value, self.policy
            )
            warnings += new_warnings

        normalized_unit = (
            normalized_value if mapping.semantic_concept_id == "financial.currency" else None
        )
        if (
            mapping.semantic_concept_id.startswith("financial.cost")
            and normalized_unit is None
            and status in {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}
        ):
            warnings += (NormalizationWarning.UNIT_UNKNOWN,)
        provenance = NormalizationProvenance(
            mapping.scope,
            item.row_reference,
            mapping.semantic_concept_id,
            mapping.decision_id,
            mapping.decision_state,
            mapping.provenance.structural_profile_fingerprint,
            mapping.provenance.semantic_fingerprint,
            mapping.provenance.classifier_version,
            mapping.provenance.ontology_version,
            mapping.provenance.governance_policy_version,
            self.policy.version,
            item.formula_expression,
            used_cached_formula_value,
        )
        record_fingerprint = fingerprint(
            mapping.scope.key,
            item.row_reference,
            canonical_value(item.source_value),
            mapping.semantic_concept_id,
            mapping.decision_id,
            mapping.provenance.ontology_version,
            mapping.provenance.governance_policy_version,
            self.policy.version,
            item.formula_expression,
            canonical_value(item.cached_formula_value) if used_cached_formula_value else None,
        )
        scope = mapping.scope
        return NormalizedEvidenceField(
            "normalized-field-" + record_fingerprint[:24],
            scope.analysis_id,
            scope.prospect_id,
            scope.organization_id,
            scope.tenant_id,
            scope.source_id,
            scope.file_id,
            scope.sheet_id,
            scope.column_id,
            item.row_reference,
            mapping.semantic_concept_id,
            item.source_value,
            normalized_value,
            normalized_type,
            normalized_unit,
            mapping.decision_id,
            mapping.decision_state,
            decision.decision_fingerprint,
            mapping.provenance.ontology_version,
            mapping.provenance.classifier_version,
            mapping.provenance.governance_policy_version,
            self.policy.version,
            status,
            warnings,
            self.clock(),
            provenance,
            record_fingerprint,
        )

    @staticmethod
    def _verify_row_scope(mapping: EffectiveSemanticMapping, item: AuthorizedSourceValue) -> None:
        context = item.row_reference.context
        row_scope = (
            context.analysis_id,
            context.prospect_id,
            context.organization_id,
            context.tenant_id,
            context.source_id,
            item.row_reference.file_id,
            item.row_reference.sheet_id,
        )
        if row_scope != mapping.scope.key[:7]:
            raise PermissionError("row provenance does not match governed mapping scope")
