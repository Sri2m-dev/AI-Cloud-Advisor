"""Deterministic, bounded, tenant-scoped enterprise intelligence queries."""

from __future__ import annotations

from time import perf_counter

from enterprise_intelligence.models import (
    ContextDimension,
    DimensionState,
    EnterpriseContext,
    ExplainedValue,
    QueryLimits,
    QueryRequest,
    QueryResponse,
    QueryType,
)

READ_ROLES = frozenset(
    {"super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"}
)
EVIDENCE_ROLES = frozenset({"super_admin", "client_admin", "auditor"})


class EnterpriseIntelligenceService:
    """READ / REASON / EXPLAIN boundary; deliberately owns no mutation API."""

    def __init__(self, context, *, role: str, graph, limits: QueryLimits | None = None):
        if role not in READ_ROLES:
            raise PermissionError("persona is not authorized for enterprise intelligence")
        self.context = context
        self.role = role
        self.graph = graph
        self.limits = limits or QueryLimits()

    def query(self, request: QueryRequest) -> QueryResponse:
        started = perf_counter()
        if request.tenant_context != self.context:
            raise PermissionError("query crosses tenant boundary")
        if request.temporal_context.get("as_of"):
            return self._unsupported_history(request)

        depth = min(max(request.depth, 0), self.limits.max_depth)
        limit = min(max(request.result_limit, 1), self.limits.max_results)
        partial = []
        if depth != request.depth:
            partial.append("maximum depth reached")
        if limit != request.result_limit:
            partial.append("maximum result count reached")

        entity = self.graph.registry.get_entity(request.entity_reference)
        node = self.graph.find_entity(entity.canonical_id)
        paths = self._paths(request.query_type, entity.canonical_id, depth)
        if any(len(getattr(path, "relationships", ())) > self.limits.max_fan_out for path in paths):
            partial.append("maximum fan-out reached")
        work = sum(max(getattr(path, "hops", 1), 1) for path in paths)
        if work > self.limits.max_work:
            partial.append("traversal work budget reached")
        paths = tuple(paths[: min(limit, self.limits.max_work)])
        if request.query_type is QueryType.CHANGE_IMPACT and not paths:
            partial.append("INCOMPLETE TOPOLOGY: no governed relationship evidence")
        if (perf_counter() - started) * 1000 > self.limits.timeout_ms:
            partial.append("query timeout budget exceeded")

        financial = node.financial_context if request.include_financial else {}
        classifications = node.classifications if request.include_classification else ()
        evidence_allowed = request.include_evidence and self.role in EVIDENCE_ROLES
        evidence = tuple(node.evidence.evidence) if evidence_allowed else ()
        facts = self._facts(entity, financial)
        derived = self._derived(classifications)
        return QueryResponse(
            query_id=QueryResponse.identifier(),
            tenant_id=self.context.tenant_id,
            query_type=request.query_type,
            subject={
                "canonical_id": entity.canonical_id,
                "name": entity.display_name,
                "type": entity.entity_type.value,
            },
            facts=facts,
            derived_findings=derived,
            paths=paths,
            context=self._context(entity, financial, classifications, paths, request),
            evidence=evidence,
            lineage=self.graph.registry.get_lineage(entity.canonical_id),
            provenance=self.graph.registry.get_provenance(entity.canonical_id),
            confidence=entity.confidence_score,
            freshness="CURRENT",
            partial=bool(partial),
            partial_reasons=tuple(dict.fromkeys(partial)),
            checkpoint_references=(f"entity-version:{entity.version}",),
            generated_at=QueryResponse.now(),
            narrative=self._narrative(
                entity, financial, paths, classifications, request.query_type
            ),
        )

    def get_enterprise_context(self, entity):
        return self._named(QueryType.ENTERPRISE_CONTEXT, entity)

    def run_named_query(self, query_type, entity):
        """Public UI/API boundary for an enumerated deterministic query."""
        return self._named(QueryType(query_type), entity)

    def explain_entity(self, entity):
        return self._named(QueryType.EXPLAIN, entity)

    def get_dependencies(self, entity):
        return self._named(QueryType.DEPENDENCIES, entity)

    def get_dependents(self, entity):
        return self._named(QueryType.DEPENDENTS, entity)

    def get_business_impact(self, entity):
        return self._named(QueryType.BUSINESS_IMPACT, entity)

    def get_financial_impact(self, entity):
        return self._named(QueryType.FINANCIAL_IMPACT, entity)

    def get_ownership_context(self, entity):
        return self._named(QueryType.OWNERSHIP, entity)

    def get_technology_context(self, entity):
        return self._named(QueryType.TECHNOLOGY, entity)

    def get_application_context(self, entity):
        return self._named(QueryType.APPLICATION, entity)

    def get_service_context(self, entity):
        return self._named(QueryType.SERVICE, entity)

    def get_risk_context(self, entity):
        return self._named(QueryType.RISK, entity)

    def get_health_context(self, entity):
        return self._named(QueryType.HEALTH, entity)

    def get_governance_context(self, entity):
        return self._named(QueryType.GOVERNANCE, entity)

    def find_change_impact(self, entity, proposed_change_context):
        return self.query(
            QueryRequest(
                self.context,
                QueryType.CHANGE_IMPACT,
                entity,
                filters={"proposed_change": dict(proposed_change_context)},
            )
        )

    def find_entities(self, predicate, *, limit=100):
        bounded = min(max(limit, 1), self.limits.max_results)
        return tuple(entity for entity in self.graph.search_graph("") if predicate(entity))[
            :bounded
        ]

    def find_unowned_entities(self, limit=100):
        return self.find_entities(lambda entity: not entity.ownership_reference, limit=limit)

    def find_unclassified_entities(self, limit=100):
        return self.find_entities(
            lambda entity: entity.classification_status == "UNCLASSIFIED", limit=limit
        )

    def find_conflicted_entities(self, limit=100):
        return self.find_entities(
            lambda entity: entity.classification_status == "CONFLICTED", limit=limit
        )

    def find_high_cost_entities(self, threshold=0, limit=100):
        return self.find_entities(
            lambda entity: self.graph.find_financial_impact(entity.canonical_id) >= threshold,
            limit=limit,
        )

    def find_high_risk_entities(self, limit=100):
        return self.find_entities(lambda entity: bool(entity.risk_reference), limit=limit)

    def find_business_critical_entities(self, limit=100):
        return self.find_entities(
            lambda entity: str(entity.metadata.get("criticality", "")).casefold() == "critical",
            limit=limit,
        )

    def _named(self, query_type, entity):
        return self.query(QueryRequest(self.context, query_type, entity))

    def _paths(self, query_type, entity_id, depth):
        if query_type is QueryType.DEPENDENCIES:
            return self.graph.find_dependencies(entity_id, depth)
        if query_type in {QueryType.DEPENDENTS, QueryType.CHANGE_IMPACT}:
            return self.graph.relationships.get_impact(entity_id, depth).paths
        if query_type is QueryType.BUSINESS_IMPACT:
            business_ids = {
                item.canonical_id for item in self.graph.find_business_impact(entity_id, depth)
            }
            return tuple(
                path
                for path in self.graph.relationships.traverse(entity_id, max_hops=depth)
                if path.entities[-1].canonical_id in business_ids
            )
        return self.graph.relationships.traverse(entity_id, max_hops=depth)

    @staticmethod
    def _facts(entity, financial):
        facts = [
            ExplainedValue(
                "FACT",
                "canonical_identity",
                entity.canonical_id,
                entity.source_system,
                entity.confidence_score,
                version_reference=f"entity:{entity.version}",
            )
        ]
        if financial:
            facts.append(
                ExplainedValue(
                    "FACT",
                    "financial_context",
                    dict(financial),
                    "financial_data_fabric",
                    1.0,
                    freshness="CURRENT",
                )
            )
        return tuple(facts)

    @staticmethod
    def _derived(classifications):
        return tuple(
            ExplainedValue(
                "DERIVED",
                str(row.get("field_name")),
                row.get("inferred_value"),
                str(row.get("inference_method") or "classification_engine"),
                float(row.get("confidence_score") or 0),
                tuple(row.get("evidence_ids") or ()),
                version_reference=f"classification:{row.get('version', 1)}",
            )
            for row in classifications
        )

    @staticmethod
    def _dimension(name, values, *, supported=True, stale=False):
        if not supported:
            return ContextDimension(name, DimensionState.UNSUPPORTED, {}, "Source is unsupported")
        if stale:
            return ContextDimension(name, DimensionState.STALE, values or {}, "Source is stale")
        if values:
            return ContextDimension(name, DimensionState.AVAILABLE, values)
        return ContextDimension(name, DimensionState.MISSING, {}, "No governed context available")

    def _context(self, entity, financial, classifications, paths, request):
        search = entity.metadata.get("search") or {}
        business = {
            key: value
            for key, value in search.items()
            if key
            in {
                "business_unit",
                "department",
                "application",
                "business_service",
                "owner",
                "cost_center",
            }
            and value not in (None, "", "UNKNOWN")
        }
        technology = (
            {
                "relationship_paths": len(paths),
                "cloud_account": entity.source_identifier,
            }
            if entity.entity_type.value == "cloud_account" or paths
            else {}
        )
        classification = {
            str(row.get("field_name")): {
                "value": row.get("inferred_value"),
                "confidence": row.get("confidence_score"),
                "status": row.get("approval_status") or row.get("status"),
            }
            for row in classifications
        }
        return EnterpriseContext(
            self._dimension(
                "IDENTITY",
                {
                    "canonical_id": entity.canonical_id,
                    "aliases": tuple(entity.identity.aliases if entity.identity else ()),
                },
            ),
            self._dimension("BUSINESS", business),
            self._dimension("TECHNOLOGY", technology),
            self._dimension("FINANCIAL", financial),
            self._dimension("CLASSIFICATION", classification),
            self._dimension(
                "OPERATIONS",
                {"health": entity.health_reference}
                if request.include_health and entity.health_reference
                else {},
                supported=request.include_health,
            ),
            self._dimension(
                "RISK",
                {"risk": entity.risk_reference}
                if request.include_risk and entity.risk_reference
                else {},
                supported=request.include_risk,
            ),
            self._dimension(
                "GOVERNANCE",
                {"lineage": entity.lineage_reference, "provenance": entity.provenance_reference},
            ),
        )

    def _narrative(self, entity, financial, paths, classifications, query_type):
        if query_type in {QueryType.CHANGE_IMPACT, QueryType.BUSINESS_IMPACT} and not paths:
            return (
                f"{entity.display_name} has no governed downstream dependencies "
                "currently recorded. Topology is incomplete."
            )
        amount = self.graph._amount(financial)
        suffix = f" Referenced spend is {amount:,.2f} USD." if amount else ""
        return (
            f"{entity.display_name} has {len(paths)} governed relationship path(s) "
            f"and {len(classifications)} classification finding(s).{suffix}"
        )

    def _unsupported_history(self, request):
        reason = "Historical reconstruction is unsupported by one or more source domains"
        return QueryResponse(
            QueryResponse.identifier(),
            self.context.tenant_id,
            request.query_type,
            {},
            (),
            (),
            (),
            None,
            (),
            None,
            None,
            None,
            "UNSUPPORTED",
            True,
            (reason,),
            (),
            QueryResponse.now(),
            reason,
        )
