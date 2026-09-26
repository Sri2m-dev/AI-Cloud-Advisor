"""Semantic adapters over canonical intelligence; no persistence or inferred allocation."""

from dataclasses import asdict
from decimal import Decimal

from data_fabric.contracts import EntityType
from enterprise_copilot.semantic_planner import CapabilityDescriptor, SemanticPlanError
from enterprise_intelligence.models import AvailabilityState, ReconciliationState
from enterprise_intelligence.queries import FINANCIAL_QUERIES
from enterprise_intelligence.search import EVIDENCE_ROLES, FINANCIAL_ROLES
from enterprise_intelligence.search_models import SearchRequest
from enterprise_intelligence.service import READ_ROLES

SPEND_DIMENSIONS = tuple(
    name.removeprefix("spend_by_") for name in FINANCIAL_QUERIES if name.startswith("spend_by_")
)


class GovernedEnterpriseCapabilities:
    def __init__(self, context, *, role, query_service, search):
        if role not in READ_ROLES or search.role != role or search.context != context:
            raise PermissionError("Enterprise capability scope is not authorized")
        financial_context = query_service.financial_context
        if financial_context is not None:
            query_service._assert_scope(context, financial_context)
            if getattr(financial_context, "role", role) != role:
                raise PermissionError("Financial authority role differs from caller")
        self.context = context
        self.role = role
        self.query_service = query_service
        self.search = search

    def catalogue(self):
        descriptors = [
            CapabilityDescriptor(
                "enterprise_context",
                "Canonical enterprise entities, financial context "
                "and recorded relationship coverage",
                "enterprise",
                (),
                (),
                ("LOOKUP",),
                (),
                False,
                False,
                self.role,
                "Missing financial context and incomplete relationships remain UNKNOWN",
                "Canonical identity, source, provenance and role-authorized evidence are retained",
                parameters=("query", "result_limit"),
            )
        ]
        if self.role in FINANCIAL_ROLES:
            descriptors.append(
                CapabilityDescriptor(
                    "enterprise_spend",
                    "Governed spend from the active financial evidence authority. "
                    "SUMMARY returns the governed observed total without claiming "
                    "complete enterprise technology coverage when the authority reports "
                    "partial or cloud-only coverage. GROUP and RANK operations require "
                    "an evidenced allocation dimension with sufficient coverage.",
                    "financial",
                    ("spend",),
                    SPEND_DIMENSIONS,
                    ("SUMMARY", "GROUP", "RANK_DESC", "RANK_ASC"),
                    SPEND_DIMENSIONS,
                    True,
                    False,
                    self.role,
                    "Absent allocation is UNKNOWN; incomplete coverage cannot establish "
                    "a ranking; no forecasts or temporal precision",
                    "Canonical financial observations, evidence references "
                    "and result fingerprint are retained",
                    parameters=("result_limit",),
                )
            )
        return tuple(descriptors)

    def handlers(self):
        return {item.capability_id: self._handler(item) for item in self.catalogue()}

    def _handler(self, descriptor):
        def execute(*, operation, parameters, dependencies, scope, constraints):
            if scope != self.context:
                raise PermissionError("Enterprise capability crossed tenant boundary")
            if operation not in descriptor.operations or dependencies:
                raise SemanticPlanError("Unsupported enterprise operation or dependency")
            if set(parameters) - set(descriptor.parameters):
                raise SemanticPlanError("Unsupported enterprise parameter")
            limit = parameters.get("result_limit", 25)
            if type(limit) is not int or not 1 <= limit <= 25:
                raise SemanticPlanError("Invalid enterprise result limit")
            if descriptor.capability_id == "enterprise_context":
                if any(constraints.values()):
                    raise SemanticPlanError("Context lookup does not aggregate or filter")
                query = parameters.get("query", "")
                if not isinstance(query, str):
                    raise SemanticPlanError("Invalid enterprise lookup")
                return self._lookup(query, limit)
            return self._spend(operation, constraints, limit)

        return execute

    @staticmethod
    def _result(capability, records=(), references=(), unknowns=(), availability="AVAILABLE"):
        return {
            "capability": capability,
            "availability": availability,
            "records": tuple(records),
            "evidence_references": tuple(dict.fromkeys(references)),
            "unknowns": tuple(unknowns),
        }

    def _lookup(self, query, limit):
        response = self.search.search(
            SearchRequest(
                self.context,
                query,
                result_limit=limit,
                include_financial=True,
                include_relationships=True,
                include_evidence=self.role in EVIDENCE_ROLES,
                authorization_scope=self.role,
            )
        )
        unknowns = list(response.partial_reasons)
        references = []
        records = []
        for item in response.results:
            record = asdict(item)

            registry = getattr(
                self.query_service,
                "registry",
                None,
            )

            if registry is not None:
                try:
                    entity = registry.get_entity(
                        item.canonical_id
                    )
                except (KeyError, LookupError, ValueError):
                    entity = None

                if entity is not None and entity.metadata:
                    record["governed_metadata"] = dict(
                        entity.metadata
                    )

            relationship_service = getattr(
                self.query_service,
                "relationship_service",
                None,
            )

            if relationship_service is not None:
                try:
                    paths = relationship_service.traverse(
                        item.canonical_id,
                        max_hops=3,
                    )
                except (KeyError, LookupError, ValueError):
                    paths = ()

                if paths:
                    record["governed_relationship_paths"] = tuple(
                        {
                            "entities": tuple(
                                {
                                    "canonical_id": entity.canonical_id,
                                    "name": entity.display_name,
                                    "type": entity.entity_type.value,
                                }
                                for entity in path.entities
                            ),
                            "relationships": tuple(
                                {
                                    "type": (
                                        relationship
                                        .relationship_type
                                        .value
                                    ),
                                    "evidence": tuple(
                                        relationship.evidence
                                    ),
                                    "provenance_reference": (
                                        relationship
                                        .provenance_reference
                                    ),
                                }
                                for relationship
                                in path.relationships
                            ),
                        }
                        for path in paths
                    )

                try:
                    impact = relationship_service.get_impact(
                        item.canonical_id,
                        max_hops=3,
                    )
                except (KeyError, LookupError, ValueError):
                    impact = None

                if impact is not None:
                    record["governed_impact"] = {
                        "narrative": impact.narrative,
                        "impacted": tuple(
                            {
                                "canonical_id": entity.canonical_id,
                                "name": entity.display_name,
                                "type": entity.entity_type.value,
                            }
                            for entity in impact.impacted
                        ),
                    }

            records.append(record)
            references.extend(
                ref
                for ref in (
                    item.canonical_id,
                    item.source_reference,
                    item.provenance_reference,
                    *item.evidence,
                )
                if ref
            )
            if self.role in FINANCIAL_ROLES and not item.financial_summary:
                unknowns.append(f"{item.display_name}: financial context UNKNOWN")
        # A count describes recorded coverage, not a complete dependency topology.
        unknowns.append(
            "Relationship summaries cover recorded relationships only; "
            "complete topology is UNKNOWN."
        )
        if not records:
            unknowns.append("No matching canonical enterprise entities; UNKNOWN.")
        return self._result(
            "enterprise_context",
            records,
            references,
            unknowns,
            "PARTIAL" if records and response.partial else "AVAILABLE" if records else "UNKNOWN",
        )

    def _spend(self, operation, constraints, limit):
        if self.role not in FINANCIAL_ROLES:
            raise PermissionError("Financial access denied")
        grouping = tuple(constraints.get("grouping", ()))
        dimensions = tuple(constraints.get("dimensions", ()))
        filters = tuple(constraints.get("filters", ()))
        if any(measure != "spend" for measure in constraints.get("measures", ())):
            raise SemanticPlanError("Unsupported financial measure")
        if operation == "SUMMARY":
            if grouping or dimensions or filters:
                raise SemanticPlanError("Summary cannot apply grouping constraints")
            family = "enterprise_spend_summary"
        else:
            if len(grouping) != 1 or grouping[0] not in SPEND_DIMENSIONS:
                raise SemanticPlanError("Spend requires one supported grouping dimension")
            if any(dimension != grouping[0] for dimension in dimensions):
                raise SemanticPlanError("Dimension differs from executed grouping")
            for condition in filters:
                if (
                    set(condition) != {"dimension", "operator", "value"}
                    or condition["dimension"] != grouping[0]
                    or condition["operator"] != "EQUALS"
                ):
                    raise SemanticPlanError("Unsupported spend filter")
            family = f"spend_by_{grouping[0]}"
        try:
            result = self.query_service.query(self.context, family, role=self.role, currency=None)
        except PermissionError:
            raise
        except (ValueError, RuntimeError, ArithmeticError):
            return self._result(
                "enterprise_spend",
                unknowns=("Canonical financial authority unavailable; UNKNOWN.",),
                availability="UNKNOWN",
            )
        if (result.organization_id, result.tenant_id) != (
            self.context.organization_id,
            self.context.tenant_id,
        ):
            raise PermissionError("Financial result crossed tenant boundary")
        references = (*result.evidence_references, *result.contributing_observation_ids)
        unknowns = list(result.reason_codes)
        unknowns.append(
            "Current canonical evidence only; requested temporal precision "
            "and forecasts remain UNKNOWN."
        )
        if (
            result.availability not in {AvailabilityState.AVAILABLE, AvailabilityState.PARTIAL}
            or not references
        ):
            return self._missing_allocation(grouping, filters, limit, references, unknowns)
        rows = list(result.breakdown)
        if grouping and not rows:
            return self._missing_allocation(grouping, filters, limit, references, unknowns)
        complete = (
            result.availability is AvailabilityState.AVAILABLE
            and result.reconciliation is ReconciliationState.RECONCILED
            and all(
                row.availability is AvailabilityState.AVAILABLE
                and row.value is not None
                and Decimal(str(row.value)).is_finite()
                and row.label.casefold() not in {"unknown", "unassigned", "unallocated", ""}
                for row in rows
            )
        )
        if (
            grouping
            and grouping[0] not in {"provider", "service"}
            and result.coverage != Decimal("100")
        ):
            complete = False
        for condition in filters:
            rows = [row for row in rows if str(condition["value"]) in {row.key, row.label}]
        if operation.startswith("RANK") and (not complete or not rows):
            known = tuple(
                {"key": row.key, "label": row.label, "entity_ids": row.entity_ids}
                for row in rows[:limit]
            )
            records = (
                (
                    {
                        "known_groups": known,
                        "ranking": None,
                        "amount": None,
                        "fingerprint": result.fingerprint,
                        "currency": result.currency,
                        "evidence_references": references,
                    },
                )
                if known
                else ()
            )
            return self._result(
                "enterprise_spend",
                records,
                references,
                (
                    *unknowns,
                    "Allocation is incomplete: ranking and highest/lowest spend amount "
                    "are UNKNOWN.",
                ),
                "PARTIAL" if known else "UNKNOWN",
            )
        if operation.startswith("RANK"):
            rows.sort(
                key=lambda row: (
                    -Decimal(str(row.value))
                    if operation == "RANK_DESC"
                    else Decimal(str(row.value)),
                    row.key,
                )
            )
        else:
            rows.sort(key=lambda row: row.key)
        if len(rows) > limit:
            unknowns.append(f"Showing {limit} of {len(rows)} governed groups.")
        record = {
            "query_family": result.query_family,
            "currency": result.currency,
            "period": asdict(result.period),
            "source_period_labels": result.metadata.get("source_period_labels", ()),
            "source_as_of": result.metadata.get("source_as_of", ()),
            "coverage": result.coverage,
            "reconciliation": result.reconciliation.value,
            "authority": result.authority,
            "fingerprint": result.fingerprint,
            "availability": result.availability.value,
            "total": result.value if operation == "SUMMARY" else None,
            "groups": tuple(asdict(row) for row in rows[:limit]),
            "ordering": operation if operation.startswith("RANK") else None,
            "evidence_references": references,
        }
        if operation != "SUMMARY" and not rows:
            return self._result(
                "enterprise_spend",
                references=references,
                unknowns=(*unknowns, "No matching allocation; UNKNOWN."),
                availability="UNKNOWN",
            )
        if not complete and operation != "SUMMARY":
            unknowns.append(
                "Partial allocation only; complete enterprise amounts and ranking remain UNKNOWN."
            )
        return self._result(
            "enterprise_spend", (record,), references, unknowns, result.availability.value
        )

    def _missing_allocation(self, grouping, filters, limit, references, unknowns):
        """Retain known canonical identities without turning identity into spend evidence."""
        records = ()
        if grouping and grouping[0] in {item.value for item in EntityType}:
            response = self.search.search(
                SearchRequest(
                    self.context,
                    entity_types=grouping,
                    result_limit=limit,
                    include_classification=False,
                    authorization_scope=self.role,
                )
            )
            entities = tuple(
                item
                for item in response.results
                if all(
                    str(condition["value"]) in {item.canonical_id, item.display_name}
                    for condition in filters
                )
            )
            if entities:
                references = (*references, *(item.canonical_id for item in entities))
                records = (
                    {
                        "known_groups": tuple(
                            {"key": item.canonical_id, "label": item.display_name}
                            for item in entities
                        ),
                        "ranking": None,
                        "amount": None,
                        "evidence_references": references,
                    },
                )
                unknowns.extend(response.partial_reasons)
        return self._result(
            "enterprise_spend",
            records,
            references,
            (
                *unknowns,
                "No governed spend allocation with provenance; amounts and ranking UNKNOWN.",
            ),
            "PARTIAL" if records else "UNKNOWN",
        )
