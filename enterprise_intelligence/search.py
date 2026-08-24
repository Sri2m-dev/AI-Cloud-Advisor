"""Governed deterministic retrieval over the canonical intelligence projection."""

from __future__ import annotations

from time import perf_counter

from enterprise_intelligence.search_models import SearchRequest, SearchResponse, SearchResult

BUSINESS_ROLES = frozenset(
    {"super_admin", "client_admin", "executive", "cio", "finance", "auditor"}
)
FINANCIAL_ROLES = frozenset(
    {"super_admin", "client_admin", "executive", "cio", "finance", "auditor"}
)
EVIDENCE_ROLES = frozenset({"super_admin", "client_admin", "auditor"})
MAX_RESULTS = 100


class EnterpriseSearchService:
    """Read-only search; owns no index and delegates authority to governed services."""

    def __init__(self, intelligence):
        self.intelligence = intelligence
        self.context = intelligence.context
        self.role = intelligence.role

    def search(self, request: SearchRequest) -> SearchResponse:
        if request.tenant_context != self.context:
            raise PermissionError("search crosses tenant boundary")
        if request.authorization_scope and request.authorization_scope != self.role:
            raise PermissionError("authorization scope does not match active persona")
        if request.temporal_context.get("as_of"):
            return SearchResponse(
                self.context.tenant_id,
                request.query_text,
                (),
                0,
                request.offset,
                request.result_limit,
                True,
                ("historical search is unsupported",),
            )
        limit = min(max(int(request.result_limit), 1), MAX_RESULTS)
        offset = max(int(request.offset), 0)
        query = request.query_text.strip().casefold()
        candidates = self.intelligence.graph.search_graph("")
        ranked = []
        for entity in candidates:
            if request.entity_types and entity.entity_type.value not in request.entity_types:
                continue
            classifications = (
                self.intelligence.graph.registry.get_classifications(entity.canonical_id)
                if request.include_classification
                else ()
            )
            match = self._match(entity, classifications, query)
            if query and match is None:
                continue
            if not self._passes_filters(entity, classifications, request.filters):
                continue
            ranked.append(
                (match or (1.0, ("all_entities",), "Governed entity"), entity, classifications)
            )
        ranked.sort(key=lambda row: (-row[0][0], row[1].canonical_id))
        page = ranked[offset : offset + limit]
        results = tuple(
            self._result(entity, classifications, match, request)
            for match, entity, classifications in page
        )
        partial = offset + len(results) < len(ranked) or request.result_limit > MAX_RESULTS
        reasons = ("additional governed matches are available",) if partial else ()
        return SearchResponse(
            self.context.tenant_id,
            request.query_text,
            results,
            len(ranked),
            offset,
            limit,
            partial,
            reasons,
        )

    def connected_to(self, canonical_id: str, *, result_limit=25):
        entity = self.intelligence.graph.registry.get_entity(canonical_id)
        paths = self.intelligence.graph.relationships.traverse(entity.canonical_id, max_hops=1)
        connected = {path.entities[-1].canonical_id for path in paths}
        if not connected:
            return ()
        results = []
        for connected_id in sorted(connected)[: min(result_limit, MAX_RESULTS)]:
            response = self.search(SearchRequest(self.context, connected_id, result_limit=1))
            if response.results:
                results.append(response.results[0])
        return tuple(results)

    def performance_probe(self, request: SearchRequest, *, samples=5):
        measured = []
        for _ in range(max(samples, 1)):
            started = perf_counter()
            self.search(request)
            measured.append((perf_counter() - started) * 1000)
        measured.sort()
        return {"p50_ms": measured[len(measured) // 2], "p95_ms": measured[-1]}

    @staticmethod
    def _match(entity, classifications, query):
        if not query:
            return None
        aliases = tuple(entity.identity.aliases if entity.identity else ())
        authoritative = (
            (entity.canonical_id, "canonical_id", 1000, "Exact canonical ID"),
            (entity.source_identifier, "source_id", 950, "Exact authoritative source ID"),
            (entity.canonical_name, "canonical_name", 900, "Exact canonical name"),
            (entity.display_name, "display_name", 900, "Exact display name"),
        )
        matches = []
        for value, field, score, reason in authoritative:
            text = str(value or "").casefold()
            if query == text:
                matches.append((float(score), field, reason))
            elif query in text:
                matches.append((400.0, field, f"Partial {field} match"))
        for alias in aliases:
            text = str(alias).casefold()
            if query == text:
                matches.append((800.0, "alias", "Exact alias"))
            elif query in text:
                matches.append((375.0, "alias", "Partial alias match"))
        for row in classifications:
            value = str(row.get("inferred_value") or row.get("value") or "").casefold()
            if not value or query not in value:
                continue
            status = str(row.get("approval_status") or row.get("status") or "NEEDS_REVIEW").upper()
            confidence = float(row.get("confidence_score") or 0)
            approved = status in {"APPROVED", "AUTO_APPROVED"}
            score = (
                925 if approved and query == value else 650 if query == value else 350
            ) + confidence
            label = "Approved" if approved else "Inferred"
            matches.append(
                (
                    score,
                    f"classification:{row.get('field_name')}",
                    (
                        f"{label} {row.get('field_name')} = "
                        f"{row.get('inferred_value') or row.get('value')}, "
                        f"confidence {confidence:.0%}, {status}"
                    ),
                )
            )
        if not matches:
            return None
        matches.sort(key=lambda item: (-item[0], item[1]))
        best = matches[0]
        fields = tuple(sorted({item[1] for item in matches}))
        return best[0] + min(len(fields) - 1, 5), fields, best[2]

    def _passes_filters(self, entity, classifications, filters):
        normalized = {
            str(key).casefold(): value
            for key, value in filters.items()
            if value not in (None, "", "All")
        }
        if (
            normalized.get("lifecycle")
            and entity.lifecycle_status != str(normalized["lifecycle"]).casefold()
        ):
            return False
        if (
            normalized.get("classification_state")
            and entity.classification_status != str(normalized["classification_state"]).upper()
        ):
            return False
        if normalized.get("owner_state") == "Unowned" and entity.ownership_reference:
            return False
        shortcut = normalized.get("shortcut")
        if shortcut == "Needs Review" and entity.classification_status != "NEEDS_REVIEW":
            return False
        if shortcut == "Conflicted" and entity.classification_status != "CONFLICTED":
            return False
        if shortcut == "Unknown Accounts" and not (
            entity.entity_type.value == "cloud_account"
            and entity.classification_status in {"UNCLASSIFIED", "NEEDS_REVIEW"}
        ):
            return False
        if (
            shortcut == "Critical Entities"
            and str(entity.metadata.get("criticality", "")).casefold() != "critical"
        ):
            return False
        if normalized.get("business_context") == "Missing" and entity.business_context_reference:
            return False
        fields = {str(row.get("field_name")): row.get("inferred_value") for row in classifications}
        for key in ("business_unit", "cost_center", "environment"):
            if normalized.get(f"missing_{key}") and fields.get(key) not in (None, "", "UNKNOWN"):
                return False
        financial_state = normalized.get("financial_state")
        if financial_state in {"High Spend", "Quarantined Spend"}:
            financial = self.intelligence.graph.registry.get_financial_context(entity.canonical_id)
            if financial_state == "High Spend" and not any(
                float(financial.get(key) or 0) > 0
                for key in ("unblended_spend", "total_spend", "allocated_spend", "amount")
            ):
                return False
            if (
                financial_state == "Quarantined Spend"
                and float(financial.get("quarantined_spend") or 0) <= 0
            ):
                return False
        return True

    def _result(self, entity, classifications, match, request):
        financial = {}
        if request.include_financial and self.role in FINANCIAL_ROLES:
            financial = self.intelligence.graph.registry.get_financial_context(entity.canonical_id)
        relationships = {}
        evidence = ()
        if request.include_relationships:
            rows = self.intelligence.graph.relationships.get_relationships(entity.canonical_id)
            relationships = {"count": len(rows)}
            if request.include_evidence and self.role in EVIDENCE_ROLES:
                evidence = tuple(item for row in rows for item in row.evidence)
        owner = entity.ownership_reference if self.role in BUSINESS_ROLES else None
        business = entity.business_context_reference if self.role in BUSINESS_ROLES else None
        return SearchResult(
            entity.canonical_id,
            entity.entity_type.value,
            entity.display_name,
            entity.source_identifier,
            tuple(entity.identity.aliases if entity.identity else ()),
            match[1],
            match[2],
            match[0],
            entity.classification_status,
            entity.confidence_score,
            owner,
            business,
            dict(financial),
            relationships,
            "CURRENT",
            f"{entity.source_system}:{entity.source_identifier}",
            entity.provenance_reference,
            entity.lifecycle_status,
            evidence,
        )
