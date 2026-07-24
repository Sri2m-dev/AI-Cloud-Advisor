"""Named dependency, impact, and evidence queries over a governed projection."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Iterable

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import TenantContext
from knowledge_projection import InMemoryProjectionStore
from knowledge_projection.models import ChangeKind

from governed_queries.models import (
    EvidenceReference,
    EvidenceState,
    GovernedQueryResult,
    QueryLimits,
    QueryMetadata,
    QueryPath,
)

MAX_DEPTH = 10
MAX_RESULTS = 100
MAX_FAN_OUT = 50
MAX_WORK_BUDGET = 1_000


class QueryControlError(ValueError):
    """Raised when query governance or authorization fails."""


class GovernedQueryService:
    """Read-only, tenant-bound query coordinator for WP-008 projection state."""

    def __init__(self, projection: InMemoryProjectionStore) -> None:
        self._projection = projection

    def dependency_query(
        self,
        context: TenantContext,
        entity_id: str,
        *,
        limits: QueryLimits = QueryLimits(),
        evidence: Iterable[EvidenceReference] = (),
        evaluated_at: datetime | None = None,
        as_of: datetime | None = None,
        freshness_threshold: timedelta = timedelta(days=1),
    ) -> GovernedQueryResult:
        return self._path_query(
            "dependency",
            context,
            entity_id,
            limits,
            evidence,
            evaluated_at,
            as_of,
            freshness_threshold,
        )

    def impact_query(
        self,
        context: TenantContext,
        entity_id: str,
        *,
        limits: QueryLimits = QueryLimits(),
        evidence: Iterable[EvidenceReference] = (),
        evaluated_at: datetime | None = None,
        as_of: datetime | None = None,
        freshness_threshold: timedelta = timedelta(days=1),
    ) -> GovernedQueryResult:
        return self._path_query(
            "impact",
            context,
            entity_id,
            limits,
            evidence,
            evaluated_at,
            as_of,
            freshness_threshold,
        )

    def evidence_query(
        self,
        context: TenantContext,
        subject_ids: Iterable[str],
        *,
        evidence: Iterable[EvidenceReference],
        limits: QueryLimits = QueryLimits(),
        evaluated_at: datetime | None = None,
        as_of: datetime | None = None,
        freshness_threshold: timedelta = timedelta(days=1),
    ) -> GovernedQueryResult:
        self._validate_limits(limits)
        now = self._evaluation_time(evaluated_at)
        self._reject_unsupported_history(as_of)
        state, checkpoint, projection_time = self._governed_state(context)
        requested = tuple(sorted(set(subject_ids)))
        for subject_id in requested:
            if (
                f"{ChangeKind.ENTITY.value}:{subject_id}" not in state
                and f"{ChangeKind.RELATIONSHIP.value}:{subject_id}" not in state
            ):
                raise QueryControlError(f"subject is not in governed projection: {subject_id}")
        disclosures, partial_reasons = self._disclose_evidence(
            context, requested, evidence, now, freshness_threshold
        )
        truncated = len(disclosures) > limits.max_results
        disclosures = disclosures[: limits.max_results]
        if truncated:
            partial_reasons.add("result_limit")
        metadata = self._metadata(
            "evidence",
            context,
            {"subject_ids": requested},
            checkpoint.sequence,
            checkpoint.state_hash,
            projection_time,
            now,
            as_of,
            limits,
            len(requested),
            truncated,
            "result_limit" if truncated else None,
            partial_reasons,
        )
        return GovernedQueryResult(
            metadata=metadata,
            entity_ids=tuple(
                item for item in requested if f"entity:{item}" in state
            ),
            relationship_ids=tuple(
                item for item in requested if f"relationship:{item}" in state
            ),
            entity_versions={
                item.id: item.version
                for item in state.values()
                if isinstance(item, EnterpriseEntity) and item.id in requested
            },
            relationship_versions={
                item.id: item.version
                for item in state.values()
                if isinstance(item, EnterpriseRelationship) and item.id in requested
            },
            paths=(),
            evidence=disclosures,
            inference="Evidence disclosure over supplied governed references.",
        )

    def _path_query(
        self,
        query_name: str,
        context: TenantContext,
        entity_id: str,
        limits: QueryLimits,
        evidence: Iterable[EvidenceReference],
        evaluated_at: datetime | None,
        as_of: datetime | None,
        freshness_threshold: timedelta,
    ) -> GovernedQueryResult:
        self._validate_limits(limits)
        now = self._evaluation_time(evaluated_at)
        self._reject_unsupported_history(as_of)
        state, checkpoint, projection_time = self._governed_state(context)
        entities, relationships = self._partition(context, state)
        if entity_id not in entities:
            raise QueryControlError(f"entity is not in governed projection: {entity_id}")
        adjacency: dict[str, list[EnterpriseRelationship]] = defaultdict(list)
        for relationship in relationships.values():
            adjacency[relationship.source_entity_id].append(relationship)
        for rows in adjacency.values():
            rows.sort(key=lambda item: (item.target_entity_id, item.id))

        queue = deque([(entity_id, (entity_id,), ())])
        paths: list[QueryPath] = []
        consumed = 0
        truncation_reason: str | None = None
        while queue and len(paths) < limits.max_results:
            current, entity_path, relationship_path = queue.popleft()
            if len(relationship_path) >= limits.max_depth:
                if adjacency.get(current):
                    truncation_reason = truncation_reason or "depth_limit"
                continue
            candidates = adjacency.get(current, ())
            if len(candidates) > limits.max_fan_out:
                truncation_reason = truncation_reason or "fan_out_limit"
            for relationship in candidates[: limits.max_fan_out]:
                if consumed >= limits.work_budget:
                    truncation_reason = "work_budget"
                    queue.clear()
                    break
                consumed += 1
                target = relationship.target_entity_id
                if target in entity_path:
                    continue
                next_entities = (*entity_path, target)
                next_relationships = (*relationship_path, relationship.id)
                paths.append(QueryPath(next_entities, next_relationships))
                if len(paths) >= limits.max_results:
                    truncation_reason = "result_limit"
                    break
                queue.append((target, next_entities, next_relationships))

        paths = sorted(paths, key=lambda item: (len(item.relationship_ids), item.identity))
        entity_ids = tuple(sorted({item for path in paths for item in path.entity_ids}))
        relationship_ids = tuple(
            sorted({item for path in paths for item in path.relationship_ids})
        )
        subjects = (*entity_ids, *relationship_ids)
        disclosures, partial_reasons = self._disclose_evidence(
            context, subjects, evidence, now, freshness_threshold
        )
        if truncation_reason:
            partial_reasons.add(truncation_reason)
        metadata = self._metadata(
            query_name,
            context,
            {"entity_id": entity_id},
            checkpoint.sequence,
            checkpoint.state_hash,
            projection_time,
            now,
            as_of,
            limits,
            consumed,
            truncation_reason is not None,
            truncation_reason,
            partial_reasons,
        )
        return GovernedQueryResult(
            metadata=metadata,
            entity_ids=entity_ids,
            relationship_ids=relationship_ids,
            entity_versions={
                item: entities[item].version for item in entity_ids
            },
            relationship_versions={
                item: relationships[item].version for item in relationship_ids
            },
            paths=tuple(paths),
            evidence=disclosures,
            inference=(
                "Dependency reachability derived from governed paths."
                if query_name == "dependency"
                else "Impact set derived from governed dependency paths."
            ),
        )

    def _governed_state(self, context: TenantContext):
        checkpoint = self._projection.checkpoint(context)
        if checkpoint is None:
            raise QueryControlError("governed projection checkpoint is required")
        state = self._projection.snapshot(context)
        times = [
            item.updated_at
            for item in state.values()
            if isinstance(item, EnterpriseEntity | EnterpriseRelationship)
        ]
        return state, checkpoint, max(times) if times else None

    @staticmethod
    def _partition(context: TenantContext, state):
        entities: dict[str, EnterpriseEntity] = {}
        relationships: dict[str, EnterpriseRelationship] = {}
        for item in state.values():
            context.assert_record_matches(item, "projected query record")
            if isinstance(item, EnterpriseEntity):
                entities[item.id] = item
            elif isinstance(item, EnterpriseRelationship):
                relationships[item.id] = item
        for relationship in relationships.values():
            if (
                relationship.source_entity_id not in entities
                or relationship.target_entity_id not in entities
            ):
                raise QueryControlError("projected relationship has broken endpoint")
        return entities, relationships

    @staticmethod
    def _disclose_evidence(
        context: TenantContext,
        subject_ids: Iterable[str],
        evidence: Iterable[EvidenceReference],
        evaluated_at: datetime,
        threshold: timedelta,
    ):
        supplied: dict[str, list[EvidenceReference]] = defaultdict(list)
        for item in evidence:
            context.assert_record_matches(item, "evidence")
            supplied[item.subject_id].append(item)
        disclosures: list[EvidenceReference] = []
        partial: set[str] = set()
        for subject_id in sorted(set(subject_ids)):
            rows = sorted(
                supplied.get(subject_id, ()),
                key=lambda item: (item.evidence_id or "", item.observed_at or datetime.min.replace(tzinfo=timezone.utc)),
            )
            if not rows:
                disclosures.append(
                    EvidenceReference(
                        subject_id,
                        context.organization_id,
                        context.tenant_id,
                        None,
                        None,
                        EvidenceState.MISSING,
                    )
                )
                partial.add("missing_evidence")
                continue
            for row in rows:
                state = row.state
                if (
                    row.observed_at is not None
                    and evaluated_at - row.observed_at > threshold
                ):
                    state = EvidenceState.STALE
                disclosed = EvidenceReference(
                    row.subject_id,
                    row.organization_id,
                    row.tenant_id,
                    row.evidence_id,
                    row.observed_at,
                    state,
                    row.source_system,
                    row.lineage_ref,
                    row.provenance_ref,
                )
                disclosures.append(disclosed)
                if state is EvidenceState.STALE:
                    partial.add("stale_evidence")
                if state is EvidenceState.MISSING:
                    partial.add("missing_evidence")
        return tuple(disclosures), partial

    @staticmethod
    def _validate_limits(limits: QueryLimits) -> None:
        values = (
            (limits.max_depth, 1, MAX_DEPTH, "max_depth"),
            (limits.max_results, 1, MAX_RESULTS, "max_results"),
            (limits.max_fan_out, 1, MAX_FAN_OUT, "max_fan_out"),
            (limits.work_budget, 1, MAX_WORK_BUDGET, "work_budget"),
        )
        for value, minimum, maximum, name in values:
            if not minimum <= value <= maximum:
                raise QueryControlError(f"{name} exceeds governed limit")

    @staticmethod
    def _evaluation_time(value: datetime | None) -> datetime:
        result = value or datetime.now(timezone.utc)
        if result.tzinfo is None:
            raise QueryControlError("evaluated_at must be timezone-aware")
        return result

    @staticmethod
    def _reject_unsupported_history(as_of: datetime | None) -> None:
        if as_of is not None:
            raise QueryControlError(
                "historical query is unsupported without retained projection history"
            )

    @staticmethod
    def _metadata(
        query_name,
        context,
        parameters,
        sequence,
        state_hash,
        projection_time,
        evaluated_at,
        as_of,
        limits,
        consumed,
        truncated,
        truncation_reason,
        partial_reasons,
    ):
        reasons = tuple(sorted(partial_reasons))
        return QueryMetadata(
            query_name=query_name,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            parameters={
                **parameters,
                "max_depth": limits.max_depth,
                "max_results": limits.max_results,
                "max_fan_out": limits.max_fan_out,
                "work_budget": limits.work_budget,
            },
            checkpoint_sequence=sequence,
            projection_state_hash=state_hash,
            projection_time=projection_time,
            evaluated_at=evaluated_at,
            as_of=as_of,
            work_budget=limits.work_budget,
            work_consumed=consumed,
            truncated=truncated,
            truncation_reason=truncation_reason,
            partial=bool(reasons),
            partial_reasons=reasons,
        )
