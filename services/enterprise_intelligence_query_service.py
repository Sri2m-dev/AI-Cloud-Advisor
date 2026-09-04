"""Read-only CMP-P5 orchestration over the P1-P4 canonical authorities."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from hashlib import sha256

from enterprise_intelligence.models import (
    AvailabilityState,
    ComparisonResult,
    IntelligenceBreakdown,
    IntelligencePeriod,
    IntelligenceResult,
    ReconciliationState,
)
from enterprise_intelligence.queries import (
    ALL_QUERY_FAMILIES,
    CONTEXT_QUERIES,
    FINANCIAL_QUERIES,
    OPTIMIZATION_QUERIES,
)


def _stable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _stable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list, set)):
        return [_stable(v) for v in value]
    return value


def _fingerprint(*parts):
    payload = json.dumps(_stable(parts), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode()).hexdigest()


def _scope(context):
    return str(
        getattr(context, "authorization_scope", None)
        or getattr(context, "key", None)
        or f"{context.organization_id}:{context.tenant_id}"
    )


class EnterpriseIntelligenceQueryService:
    """Single typed consumption contract. It persists and invents no facts."""

    CONTRACT_VERSION = "cmp-p5-v1"

    def __init__(
        self,
        *,
        financial_service=None,
        financial_context=None,
        optimization_service=None,
        relationship_service=None,
        registry=None,
        source_fact_repository=None,
        attribution_provider=None,
    ):
        self.financial_service = financial_service
        self.financial_context = financial_context
        self.optimization_service = optimization_service
        self.relationship_service = relationship_service
        self.registry = registry
        self.source_fact_repository = source_fact_repository
        self.attribution_provider = attribution_provider

    def query(
        self, context, query_family, *, period=None, currency="USD", entity_id=None, role=None
    ):
        if query_family not in ALL_QUERY_FAMILIES:
            return self._result(
                context,
                query_family,
                period,
                AvailabilityState.UNSUPPORTED,
                reason_codes=("UNSUPPORTED_QUERY_FAMILY",),
            )
        if query_family in FINANCIAL_QUERIES:
            return self._financial(context, query_family, period, currency)
        if query_family in OPTIMIZATION_QUERIES:
            return self._optimization(context, query_family, period, entity_id)
        if query_family in CONTEXT_QUERIES:
            return self._context(context, query_family, period, entity_id)
        return self._trust(context, query_family, period, entity_id, role)

    def enterprise_spend_summary(self, context, *, period=None, currency="USD"):
        return self.query(context, "enterprise_spend_summary", period=period, currency=currency)

    def spend_by(self, context, dimension, *, period=None, currency="USD"):
        return self.query(context, f"spend_by_{dimension}", period=period, currency=currency)

    def optimization_summary(self, context, *, period=None):
        return self.query(context, "optimization_summary", period=period)

    def period_comparison(
        self,
        context,
        query_family,
        *,
        current_period,
        comparison_period,
        currency="USD",
        entity_id=None,
    ):
        current = self.query(
            context, query_family, period=current_period, currency=currency, entity_id=entity_id
        )
        previous = self.query(
            context, query_family, period=comparison_period, currency=currency, entity_id=entity_id
        )
        reasons = []
        if current.currency != previous.currency or current.unit != previous.unit:
            reasons.append("INCOMPATIBLE_CURRENCY_OR_UNIT")
        if current.scope != previous.scope:
            reasons.append("INCOMPATIBLE_SCOPE")
        if (
            current.availability is not AvailabilityState.AVAILABLE
            or previous.availability is not AvailabilityState.AVAILABLE
        ):
            reasons.append("INCOMPLETE_PERIOD_AUTHORITY")
        if (
            current.coverage is not None
            and previous.coverage is not None
            and current.coverage != previous.coverage
        ):
            reasons.append("MATERIALLY_DIFFERENT_COVERAGE")
        if not isinstance(current.value, Decimal) or not isinstance(previous.value, Decimal):
            reasons.append("NON_NUMERIC_RESULT")
        if reasons:
            state, absolute, percentage = AvailabilityState.NOT_COMPARABLE, None, None
        else:
            state = AvailabilityState.AVAILABLE
            absolute = current.value - previous.value
            percentage = None if previous.value == 0 else absolute / previous.value * Decimal("100")
        return ComparisonResult(
            current,
            previous,
            state,
            absolute,
            percentage,
            tuple(reasons),
            _fingerprint(current.fingerprint, previous.fingerprint, reasons, absolute, percentage),
        )

    def _financial(self, context, family, period, currency):
        if self.financial_service is None or self.financial_context is None:
            return self._result(
                context,
                family,
                period,
                AvailabilityState.UNKNOWN,
                reason_codes=("FINANCIAL_AUTHORITY_UNAVAILABLE",),
                authority="P1",
            )
        self._assert_scope(context, self.financial_context)
        posture = self.financial_service.get_financial_posture(
            self.financial_context, period, currency=currency
        )
        if not posture.has_data:
            return self._result(
                context,
                family,
                period,
                AvailabilityState.UNKNOWN,
                currency=posture.currency,
                reason_codes=("NO_CANONICAL_FINANCIAL_OBSERVATIONS",),
                authority="P1",
            )
        evidence = tuple(self.financial_service.get_financial_evidence(self.financial_context))
        observations = tuple(
            dict.fromkeys(
                str(row.get("observation_id")) for row in evidence if row.get("observation_id")
            )
        )
        refs = tuple(
            dict.fromkeys(
                str(row.get("evidence_reference"))
                for row in evidence
                if row.get("evidence_reference")
            )
        )
        if family == "enterprise_spend_summary":
            breakdown = (
                IntelligenceBreakdown("cloud", "Cloud Spend", posture.cloud_spend),
                IntelligenceBreakdown(
                    "shared",
                    "Shared Spend",
                    posture.unallocated_resolved_spend,
                    AvailabilityState.PARTIAL
                    if posture.unallocated_resolved_spend
                    else AvailabilityState.AVAILABLE,
                ),
                IntelligenceBreakdown(
                    "unresolved",
                    "Unresolved Spend",
                    posture.quarantined_spend,
                    AvailabilityState.PARTIAL
                    if posture.quarantined_spend
                    else AvailabilityState.AVAILABLE,
                ),
            )
            reconciled = posture.reconciliation_variance == 0
            available = not posture.quarantined_spend and not posture.unreconciled_spend
            return self._result(
                context,
                family,
                period,
                AvailabilityState.AVAILABLE if available else AvailabilityState.PARTIAL,
                value=posture.total_ingested_spend,
                currency=posture.currency,
                breakdown=breakdown,
                observations=observations,
                coverage=posture.allocation_coverage_percentage,
                reconciliation=ReconciliationState.RECONCILED
                if reconciled
                else ReconciliationState.NOT_RECONCILABLE,
                evidence=refs,
                reasons=posture.warnings,
                authority=f"P1:{posture.contract_version}",
                metadata={
                    "cloud_spend": posture.cloud_spend,
                    "shared_spend": posture.unallocated_resolved_spend,
                    "unresolved_spend": posture.quarantined_spend,
                    "source_rows": posture.source_rows,
                },
            )
        dimension = family.removeprefix("spend_by_")
        rows = self._dimension_rows(dimension, period)
        if rows is None:
            return self._result(
                context,
                family,
                period,
                AvailabilityState.UNKNOWN,
                currency=posture.currency,
                observations=observations,
                evidence=refs,
                reason_codes=("CONTEXT_DIMENSION_UNAVAILABLE",),
                authority="P1/P3",
            )
        breakdown = tuple(self._breakdown(row) for row in rows)
        total = sum(
            (Decimal(str(row.value)) for row in breakdown if row.value is not None), Decimal()
        )
        reconciled = total == posture.total_ingested_spend
        return self._result(
            context,
            family,
            period,
            AvailabilityState.AVAILABLE if reconciled else AvailabilityState.PARTIAL,
            value=total,
            currency=posture.currency,
            breakdown=breakdown,
            observations=observations,
            coverage=posture.allocation_coverage_percentage,
            reconciliation=ReconciliationState.RECONCILED
            if reconciled
            else ReconciliationState.PARTIAL,
            evidence=refs,
            reason_codes=() if reconciled else ("GROUPING_DOES_NOT_COVER_CANONICAL_TOTAL",),
            authority="P1/P3",
        )

    def _dimension_rows(self, dimension, period):
        provider = self.attribution_provider or self.financial_service
        names = [f"get_spend_by_{dimension}"]
        if dimension == "business_service":
            names.append("get_spend_by_service")
        for name in names:
            method = getattr(provider, name, None)
            if method:
                return tuple(method(self.financial_context, period))
        return None

    @staticmethod
    def _breakdown(row):
        label = (
            row.get("label")
            or row.get("name")
            or row.get("service")
            or row.get("dimension")
            or row.get("entity_id")
            or "UNKNOWN"
        )
        amount = row.get("amount", row.get("spend", row.get("value")))
        return IntelligenceBreakdown(
            str(row.get("key") or label),
            str(label),
            Decimal(str(amount)) if amount is not None else None,
            AvailabilityState.AVAILABLE if amount is not None else AvailabilityState.UNKNOWN,
            tuple(str(v) for v in row.get("entity_ids", ())),
            tuple(str(v) for v in row.get("observation_ids", ())),
        )

    def _optimization(self, context, family, period, entity_id):
        if self.optimization_service is None:
            return self._result(
                context,
                family,
                period,
                AvailabilityState.UNKNOWN,
                reason_codes=("OPTIMIZATION_AUTHORITY_UNAVAILABLE",),
                authority="P2",
            )
        repository = getattr(self.optimization_service, "repository", self.optimization_service)
        opportunities = tuple(repository.list(context))
        if entity_id:
            opportunities = tuple(row for row in opportunities if row.affected_entity == entity_id)
        ids = tuple(row.opportunity_id for row in opportunities)
        if family == "opportunities_for_entity":
            if not entity_id:
                return self._result(
                    context,
                    family,
                    period,
                    AvailabilityState.UNKNOWN,
                    reason_codes=("ENTITY_REQUIRED",),
                    authority="P2",
                )
            return self._result(
                context,
                family,
                period,
                AvailabilityState.AVAILABLE,
                value=len(opportunities),
                opportunities=ids,
                entity_ids=(entity_id,),
                authority="P2",
                metadata={"opportunities": opportunities},
            )
        if family == "optimization_summary":
            summary = repository.savings_summary(context)
            stages = {
                key.removesuffix("_by_currency"): tuple(value)
                for key, value in summary.items()
                if key.endswith("_by_currency")
            }
            return self._result(
                context,
                family,
                period,
                AvailabilityState.AVAILABLE,
                value=summary.get("opportunity_count", len(opportunities)),
                opportunities=ids,
                authority="P2",
                metadata={"stages": stages},
            )
        dimension = family.removeprefix("savings_by_")
        groups = {}
        for row in opportunities:
            key = self._opportunity_dimension(row, dimension)
            if key is None or row.potential_savings is None:
                continue
            groups[(str(key), row.currency)] = (
                groups.get((str(key), row.currency), Decimal()) + row.potential_savings
            )
        currencies = {key[1] for key in groups}
        if len(currencies) > 1:
            return self._result(
                context,
                family,
                period,
                AvailabilityState.CONFLICTED,
                opportunities=ids,
                reason_codes=("MULTIPLE_CURRENCIES",),
                authority="P2",
            )
        breakdown = tuple(
            IntelligenceBreakdown(
                key[0],
                key[0],
                value,
                opportunity_ids=tuple(
                    row.opportunity_id
                    for row in opportunities
                    if self._opportunity_dimension(row, dimension) == key[0]
                ),
            )
            for key, value in sorted(groups.items())
        )
        return self._result(
            context,
            family,
            period,
            AvailabilityState.AVAILABLE if breakdown else AvailabilityState.UNKNOWN,
            value=sum((item.value for item in breakdown), Decimal()) if breakdown else None,
            currency=next(iter(currencies), None),
            breakdown=breakdown,
            opportunities=ids,
            reason_codes=() if breakdown else ("DIMENSION_UNAVAILABLE",),
            authority="P2",
        )

    @staticmethod
    def _opportunity_dimension(row, dimension):
        entity_type = str(row.affected_entity_type).casefold().replace(" ", "_")
        if dimension in {"application", "technology"} and entity_type == dimension:
            return row.affected_entity
        values = dict(row.calculation_inputs)
        return values.get(dimension) or values.get(f"{dimension}_id")

    def _context(self, context, family, period, entity_id):
        if not entity_id:
            return self._result(
                context,
                family,
                period,
                AvailabilityState.UNKNOWN,
                reason_codes=("ENTITY_REQUIRED",),
                authority="P3",
            )
        service = self.relationship_service
        if service is None:
            return self._result(
                context,
                family,
                period,
                AvailabilityState.UNKNOWN,
                entity_ids=(entity_id,),
                reason_codes=("RELATIONSHIP_AUTHORITY_UNAVAILABLE",),
                authority="P3",
            )
        method_name = {
            "owner_for_entity": "get_owners",
            "dependencies_for_entity": "get_dependencies",
            "impact_of_change": "get_impact",
        }.get(family)
        if method_name:
            value = getattr(service, method_name)(entity_id)
        else:
            relationship_type = "funded_by" if family == "cost_center_for_entity" else "supports"
            value = service.get_relationships(entity_id, relationship_type=relationship_type)
        empty = value is None or value == () or value == []
        ids = self._entity_ids(value)
        return self._result(
            context,
            family,
            period,
            AvailabilityState.UNKNOWN if empty else AvailabilityState.AVAILABLE,
            value=None if empty else value,
            entity_ids=(entity_id, *ids),
            reason_codes=("NO_CONFIRMED_EFFECTIVE_RELATIONSHIP",) if empty else (),
            authority="P3",
        )

    def _trust(self, context, family, period, entity_id, role):
        repo = self.source_fact_repository
        if repo is None:
            evidence = ()
            if self.financial_service is not None and self.financial_context is not None:
                self._assert_scope(context, self.financial_context)
                evidence = tuple(
                    self.financial_service.get_financial_evidence(self.financial_context)
                )
            if not evidence:
                return self._result(
                    context,
                    family,
                    period,
                    AvailabilityState.UNKNOWN,
                    reason_codes=("SOURCE_AUTHORITY_UNAVAILABLE",),
                    authority="P4/P1",
                )
            refs = tuple(
                str(row.get("observation_id")) for row in evidence if row.get("observation_id")
            )
            denied = {"credential", "credential_reference", "raw", "secret", "payload"}
            safe = tuple(
                {key: value for key, value in row.items() if key.casefold() not in denied}
                for row in evidence
            )
            return self._result(
                context,
                family,
                period,
                AvailabilityState.AVAILABLE,
                value=safe,
                observations=refs,
                evidence=refs,
                authority="P1_LINEAGE",
            )
        facts = tuple(repo.list_current_facts(context.organization_id, context.tenant_id))
        if entity_id:
            facts = tuple(
                row
                for row in facts
                if row.subject_reference == entity_id or row.object_reference == entity_id
            )
        stale = tuple(
            row.source_fact_id for row in facts if row.freshness.value.casefold() == "stale"
        )
        quarantined = tuple(
            row.source_fact_id
            for row in facts
            if row.lifecycle.value.casefold() in {"connector_failed", "source_disabled"}
        )
        if family == "unresolved_context":
            selected = tuple(row for row in facts if row.value in (None, "", "UNKNOWN"))
        elif family == "conflicted_context":
            by_key = {}
            for row in facts:
                by_key.setdefault((row.subject_reference, row.predicate), set()).add(
                    str(row.value or row.object_reference)
                )
            selected = tuple(
                row for row in facts if len(by_key[(row.subject_reference, row.predicate)]) > 1
            )
        else:
            selected = facts
        state = (
            AvailabilityState.QUARANTINED
            if quarantined
            else AvailabilityState.STALE
            if stale
            else AvailabilityState.AVAILABLE
            if selected
            else AvailabilityState.UNKNOWN
        )
        refs = tuple(row.source_fact_id for row in selected)
        value = tuple(
            {
                "source_fact_id": row.source_fact_id,
                "source_type": row.source_type,
                "source_instance_id": row.source_instance_id,
                "freshness": row.freshness.value,
                "evidence_reference": row.evidence_reference,
            }
            for row in selected
        )
        return self._result(
            context,
            family,
            period,
            state,
            value=value,
            evidence=refs,
            freshness="STALE" if stale else "FRESH",
            conflicts=refs if family == "conflicted_context" else (),
            reason_codes=("QUARANTINED_SOURCE",)
            if quarantined
            else ("STALE_SOURCE",)
            if stale
            else (),
            authority="P4",
        )

    @staticmethod
    def _entity_ids(value):
        values = value if isinstance(value, (tuple, list)) else (value,)
        result = []
        for row in values:
            for name in ("canonical_id", "target_entity_id", "source_entity_id"):
                item = getattr(row, name, None)
                if item and str(item) not in result:
                    result.append(str(item))
        return tuple(result)

    @staticmethod
    def _assert_scope(requested, authority):
        if (
            requested.organization_id != authority.organization_id
            or requested.tenant_id != authority.tenant_id
        ):
            raise PermissionError("canonical authority is outside the active tenant scope")

    def _result(
        self,
        context,
        family,
        period,
        availability,
        *,
        value=None,
        currency=None,
        unit=None,
        breakdown=(),
        observations=(),
        opportunities=(),
        entity_ids=(),
        coverage=None,
        reconciliation=ReconciliationState.NOT_APPLICABLE,
        freshness=None,
        conflicts=(),
        evidence=(),
        explanations=(),
        reasons=(),
        reason_codes=(),
        authority="",
        metadata=None,
    ):
        start, end = period or (None, None)
        model_period = IntelligencePeriod(start, end)
        codes = tuple(reason_codes) or tuple(str(item) for item in reasons)
        seed = (
            context.tenant_id,
            context.organization_id,
            _scope(context),
            family,
            asdict(model_period),
            currency,
            unit,
            value,
            breakdown,
            observations,
            opportunities,
            entity_ids,
            coverage,
            reconciliation,
            freshness,
            conflicts,
            evidence,
            explanations,
            codes,
            authority,
            metadata or {},
            self.CONTRACT_VERSION,
        )
        return IntelligenceResult(
            str(context.tenant_id),
            str(context.organization_id),
            _scope(context),
            family,
            model_period,
            availability,
            value,
            currency,
            unit,
            tuple(breakdown),
            tuple(observations),
            tuple(opportunities),
            tuple(dict.fromkeys(str(v) for v in entity_ids)),
            coverage,
            reconciliation,
            freshness,
            tuple(conflicts),
            tuple(evidence),
            tuple(explanations),
            codes,
            _fingerprint(*seed),
            authority,
            metadata or {},
        )
