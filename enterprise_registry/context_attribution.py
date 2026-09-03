"""Dimension-safe financial and optimization context projection."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping

from data_fabric.foundation import TenantContext


class AttributionState(str, Enum):
    RESOLVED = "resolved"
    SHARED_UNALLOCATED = "shared_unallocated"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class MonetaryFact:
    fact_id: str
    organization_id: str
    tenant_id: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class ContextAttribution:
    fact_id: str
    entity_ids: tuple[str, ...]
    state: AttributionState


@dataclass(frozen=True, slots=True)
class Allocation:
    destination_entity_id: str
    weight: Decimal


@dataclass(frozen=True, slots=True)
class Reconciliation:
    enterprise_total: Decimal
    resolved: Decimal
    shared: Decimal
    unresolved: Decimal
    variance: Decimal
    observation_ids: tuple[str, ...]


class EnterpriseContextAttributionService:
    def __init__(self, context: TenantContext, *, tolerance: Decimal = Decimal("0.01")):
        self.context, self.tolerance = context, tolerance

    def validate_allocations(self, allocations: Iterable[Allocation]) -> tuple[Allocation, ...]:
        rows = tuple(allocations)
        destinations = [row.destination_entity_id for row in rows]
        if len(destinations) != len(set(destinations)):
            raise ValueError("duplicate allocation destination")
        if any(row.weight < 0 for row in rows):
            raise ValueError("allocation weights cannot be negative")
        if abs(sum((row.weight for row in rows), Decimal(0)) - Decimal(1)) > self.tolerance:
            raise ValueError("allocation weights must equal 100%")
        return rows

    def reconcile(
        self, facts: Iterable[MonetaryFact], attributions: Iterable[ContextAttribution]
    ) -> Reconciliation:
        unique: dict[str, MonetaryFact] = {}
        for fact in facts:
            self.context.assert_record_matches(fact, "monetary fact")
            if fact.fact_id in unique and unique[fact.fact_id] != fact:
                raise ValueError(f"conflicting monetary fact: {fact.fact_id}")
            unique[fact.fact_id] = fact
        by_fact: dict[str, ContextAttribution] = {}
        for attribution in attributions:
            if attribution.fact_id not in unique:
                raise ValueError(f"unknown monetary fact: {attribution.fact_id}")
            if attribution.fact_id in by_fact and by_fact[attribution.fact_id] != attribution:
                raise ValueError(f"multiple authoritative attributions: {attribution.fact_id}")
            by_fact[attribution.fact_id] = attribution
        totals = {state: Decimal(0) for state in AttributionState}
        for fact_id, fact in unique.items():
            state = by_fact.get(
                fact_id, ContextAttribution(fact_id, (), AttributionState.UNRESOLVED)
            ).state
            totals[state] += fact.amount
        enterprise = sum((fact.amount for fact in unique.values()), Decimal(0))
        variance = enterprise - sum(totals.values(), Decimal(0))
        if abs(variance) > self.tolerance:
            raise ValueError("financial reconciliation failed")
        return Reconciliation(
            enterprise,
            totals[AttributionState.RESOLVED],
            totals[AttributionState.SHARED_UNALLOCATED],
            totals[AttributionState.UNRESOLVED],
            variance,
            tuple(sorted(unique)),
        )

    @staticmethod
    def totals_by_entity(
        facts: Iterable[MonetaryFact], attributions: Iterable[ContextAttribution]
    ) -> Mapping[str, Decimal]:
        amounts = {fact.fact_id: fact.amount for fact in facts}
        result: dict[str, Decimal] = {}
        for row in attributions:
            if row.state is not AttributionState.RESOLVED:
                continue
            for entity_id in set(row.entity_ids):
                result[entity_id] = result.get(entity_id, Decimal(0)) + amounts[row.fact_id]
        return result
