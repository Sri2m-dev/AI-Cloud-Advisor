from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _norm(value: Any) -> str:
    return _text(value).lower()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _slug(value: Any) -> str:
    return "_".join(_text(value, "unknown").lower().replace("/", " ").replace(":", " ").split())


def _first(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _node_id(node_type: str, name: str) -> str:
    return f"{_slug(node_type)}:{_slug(name)}"


class EnterpriseGraphRepository:
    ORG_TABLES = {
        "enterprise_asset_identity",
        "enterprise_asset_correlation",
        "enterprise_asset_ownership",
        "enterprise_cost_attribution",
        "business_capability_registry",
        "ai_decision_history",
        "ai_workflow_actions",
        "ai_recommendation_history",
        "execution_log",
        "connector_registry",
        "connector_sync_history",
        "technology_relationships",
        "relationship_graph",
    }

    GLOBAL_TABLES = {
        "technology_inventory",
        "application_registry",
        "application_master",
        "application_spend_mapping",
        "business_services",
        "business_service_relationships",
    }

    @staticmethod
    def load_context(organization_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        org_id = resolve_organization_id(organization_id)
        context = {"organization_id": org_id}
        for table in sorted(EnterpriseGraphRepository.ORG_TABLES):
            context[table] = EnterpriseGraphRepository._fetch_table(table, org_id)
        for table in sorted(EnterpriseGraphRepository.GLOBAL_TABLES):
            context[table] = EnterpriseGraphRepository._fetch_table(table)
        return context

    @staticmethod
    def load_nodes_and_edges(organization_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        context = EnterpriseGraphRepository.load_context(organization_id)
        builder = _GraphBuilder(context["organization_id"])
        builder.build(context)
        return {"nodes": builder.nodes(), "edges": builder.edges()}

    @staticmethod
    def _fetch_table(table_name: str, organization_id: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        try:
            query = supabase.table(table_name).select("*")
            if organization_id:
                query = query.eq("organization_id", organization_id)
            return query.limit(limit).execute().data or []
        except Exception:
            if organization_id:
                try:
                    return supabase.table(table_name).select("*").limit(limit).execute().data or []
                except Exception:
                    return []
            return []


class _GraphBuilder:
    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    def build(self, context: dict[str, Any]) -> None:
        self.add_node("Organization", self.organization_id, organization_id=self.organization_id)
        self._business_capabilities(context)
        self._applications(context)
        self._assets(context)
        self._costs(context)
        self._technologies(context)
        self._relationships(context)
        self._ai_recommendations(context)
        self._ai_decisions(context)
        self._workflows(context)
        self._executions(context)
        self._connectors(context)

    def nodes(self) -> list[dict[str, Any]]:
        return sorted(self._nodes.values(), key=lambda row: (row["type"], row["name"]))

    def edges(self) -> list[dict[str, Any]]:
        return sorted(self._edges.values(), key=lambda row: (row["source_name"], row["relationship_type"], row["target_name"]))

    def add_node(self, node_type: str, name: Any, **metadata: Any) -> str | None:
        label = _text(name)
        if not label:
            return None
        node_id = _node_id(node_type, label)
        existing = self._nodes.get(node_id, {})
        merged_metadata = {**(existing.get("metadata") or {}), **{k: v for k, v in metadata.items() if v not in (None, "")}}
        self._nodes[node_id] = {
            "id": node_id,
            "name": label,
            "label": label,
            "type": node_type,
            "metadata": merged_metadata,
        }
        return node_id

    def add_edge(
        self,
        source_type: str,
        source_name: Any,
        relationship_type: str,
        target_type: str,
        target_name: Any,
        **metadata: Any,
    ) -> None:
        source_id = self.add_node(source_type, source_name)
        target_id = self.add_node(target_type, target_name)
        if not source_id or not target_id or source_id == target_id:
            return
        relation = _text(relationship_type, "RELATED_TO").upper()
        key = (source_id, relation, target_id)
        self._edges[key] = {
            "source": source_id,
            "target": target_id,
            "source_name": _text(source_name),
            "target_name": _text(target_name),
            "source_type": source_type,
            "target_type": target_type,
            "relationship_type": relation,
            "metadata": {k: v for k, v in metadata.items() if v not in (None, "")},
        }

    def _business_capabilities(self, context: dict[str, Any]) -> None:
        for row in context.get("business_capability_registry", []):
            capability = _first(row, "capability_name", "business_capability", default="")
            self.add_node(
                "Business Capability",
                capability,
                code=row.get("capability_code"),
                health=row.get("health_score"),
                maturity=row.get("maturity"),
                criticality=row.get("criticality"),
            )
            self.add_edge("Organization", self.organization_id, "OWNS", "Business Capability", capability)
            self.add_edge("Business Capability", capability, "BELONGS_TO", "Department", row.get("department"))
            self.add_edge("Business Capability", capability, "PART_OF", "Business Unit", row.get("business_unit"))
            self.add_edge("Business Capability", capability, "OWNED_BY", "Owner", row.get("executive_owner"))

    def _applications(self, context: dict[str, Any]) -> None:
        for table in ("application_registry", "application_master"):
            for row in context.get(table, []):
                app = _first(row, "application", "app_name", "application_name", "name", default="")
                self.add_node("Application", app, source_table=table, owner=_first(row, "owner", "application_owner"))
                self.add_edge("Organization", self.organization_id, "OWNS", "Application", app)

        for row in context.get("enterprise_asset_correlation", []):
            app = row.get("application")
            service = row.get("business_service")
            capability = row.get("business_capability")
            asset = row.get("enterprise_asset_id")
            self.add_node("Application", app, confidence=row.get("confidence"), source=row.get("correlation_source"))
            self.add_edge("Business Capability", capability, "SUPPORTS", "Business Service", service)
            self.add_edge("Business Service", service, "SUPPORTS", "Application", app)
            self.add_edge("Application", app, "USES", "Enterprise Asset", asset)
            self.add_edge("Application", app, "OWNED_BY", "Owner", row.get("owner"))
            self.add_edge("Application", app, "BELONGS_TO", "Department", row.get("department"))
            self.add_edge("Application", app, "FUNDED_BY", "Cost Center", row.get("cost_center"))
            self.add_edge("Application", app, "RUNS_IN", "Environment", row.get("environment"))
            for ai_service in row.get("ai_services") or []:
                self.add_edge("Application", app, "USES", "AI Service", ai_service)

        for row in context.get("enterprise_asset_ownership", []):
            app = row.get("application")
            service = row.get("business_service")
            capability = row.get("business_capability")
            self.add_edge("Business Capability", capability, "SUPPORTS", "Business Service", service)
            self.add_edge("Business Service", service, "SUPPORTS", "Application", app)
            self.add_edge("Application", app, "OWNS", "Enterprise Asset", row.get("enterprise_asset_id"))
            self.add_edge("Application", app, "OWNED_BY", "Owner", row.get("technical_owner"))
            self.add_edge("Application", app, "OWNED_BY", "Owner", row.get("business_owner"))
            self.add_edge("Business Capability", capability, "OWNED_BY", "Owner", row.get("executive_owner"))
            self.add_edge("Application", app, "FUNDED_BY", "Cost Center", row.get("cost_center"))
            self.add_edge("Application", app, "BELONGS_TO", "Department", row.get("department"))
            self.add_edge("Application", app, "SUPPORTED_BY", "Team", row.get("team"))

    def _assets(self, context: dict[str, Any]) -> None:
        for row in context.get("enterprise_asset_identity", []):
            asset = _first(row, "enterprise_asset_id", "asset_uid", default="")
            provider = row.get("provider")
            asset_name = row.get("asset_name") or row.get("source_asset_id")
            self.add_node(
                "Enterprise Asset",
                asset,
                asset_name=asset_name,
                provider=provider,
                resource_type=row.get("resource_type"),
                region=row.get("region"),
                last_seen=row.get("last_seen"),
            )
            self.add_edge("Organization", self.organization_id, "OWNS", "Enterprise Asset", asset)
            self.add_edge("Enterprise Asset", asset, "HOSTED_ON", "Cloud Provider", provider)
            self.add_edge("Enterprise Asset", asset, "PART_OF", "Cloud Resource", asset_name)
            self.add_edge("Cloud Resource", asset_name, "PROVIDED_BY", "Cloud Provider", provider)

    def _costs(self, context: dict[str, Any]) -> None:
        totals: dict[tuple[str, str], float] = {}
        for row in context.get("enterprise_cost_attribution", []):
            amount = _safe_float(_first(row, "cost", "amount", "total_cost", "monthly_cost", "blended_cost", default=0))
            for node_type, name in (
                ("Application", row.get("application")),
                ("Business Capability", row.get("business_capability")),
                ("Cost Center", row.get("cost_center")),
                ("Enterprise Asset", row.get("enterprise_asset_id")),
            ):
                if name:
                    totals[(node_type, _text(name))] = totals.get((node_type, _text(name)), 0.0) + amount
            self.add_edge("Enterprise Asset", row.get("enterprise_asset_id"), "GENERATES_COST", "Cloud Provider", row.get("cloud"))

        for (node_type, name), total in totals.items():
            cost_name = f"Cost: {name}"
            self.add_node("Cloud Cost", cost_name, amount=round(total, 2))
            self.add_edge(node_type, name, "GENERATES_COST", "Cloud Cost", cost_name, amount=round(total, 2))

    def _technologies(self, context: dict[str, Any]) -> None:
        for row in context.get("technology_inventory", []):
            technology = _first(row, "technology_name", "technology", "tool_name", "product", "service_name", default="")
            vendor = _first(row, "vendor_name", "vendor", "provider", default="")
            self.add_node("Technology", technology, technology_type=_first(row, "technology_type", "type", "category"), vendor=vendor)
            self.add_edge("Technology", technology, "PROVIDED_BY", "Vendor", vendor)
            self.add_edge("Technology", technology, "BELONGS_TO", "Department", _first(row, "department", "owner_department"))

    def _relationships(self, context: dict[str, Any]) -> None:
        for table in ("technology_relationships", "relationship_graph", "business_service_relationships"):
            for row in context.get(table, []):
                source = _first(row, "source_name", "source", "from_name", "parent_name", default="")
                target = _first(row, "target_name", "target", "to_name", "child_name", default="")
                self.add_edge(
                    _first(row, "source_type", "from_type", default="Entity"),
                    source,
                    _first(row, "relationship_type", "relationship", "type", default="RELATED_TO"),
                    _first(row, "target_type", "to_type", default="Entity"),
                    target,
                    source_table=table,
                )

    def _ai_recommendations(self, context: dict[str, Any]) -> None:
        for row in context.get("ai_recommendation_history", []):
            rec = row.get("recommendation_id")
            self.add_node("Recommendation", rec, title=row.get("title"), priority=row.get("priority"), confidence=row.get("confidence"))
            self.add_edge("Recommendation", rec, "OWNED_BY", "Owner", row.get("owner"))
            for app in row.get("related_applications") or []:
                self.add_edge("Recommendation", rec, "RELATED_TO", "Application", app)
            for asset in row.get("related_assets") or []:
                self.add_edge("Recommendation", rec, "RELATED_TO", "Enterprise Asset", asset)
            for capability in row.get("related_capabilities") or []:
                self.add_edge("Recommendation", rec, "RELATED_TO", "Business Capability", capability)

    def _ai_decisions(self, context: dict[str, Any]) -> None:
        for row in context.get("ai_decision_history", []):
            decision = row.get("decision_id")
            self.add_node("Decision", decision, decision=row.get("decision"), priority=row.get("priority"), confidence=row.get("confidence"))
            self.add_edge("Decision", decision, "IMPLEMENTS", "Recommendation", row.get("recommendation_id"))
            self.add_edge("Decision", decision, "APPROVED_BY", "Owner", row.get("owner"))

    def _workflows(self, context: dict[str, Any]) -> None:
        for row in context.get("ai_workflow_actions", []):
            workflow = row.get("action_id")
            self.add_node("Workflow", workflow, status=row.get("execution_status"), action_type=row.get("action_type"))
            self.add_edge("Workflow", workflow, "IMPLEMENTS", "Recommendation", row.get("recommendation_id"))
            self.add_edge("Workflow", workflow, "EXECUTES", "Decision", row.get("decision_id"))
            self.add_edge("Workflow", workflow, "OWNED_BY", "Owner", row.get("owner"))

    def _executions(self, context: dict[str, Any]) -> None:
        for row in context.get("execution_log", []):
            execution = f"Execution: {row.get('workflow_id')}:{row.get('status')}"
            self.add_node("Execution", execution, status=row.get("status"), projected_savings=row.get("projected_savings"))
            self.add_edge("Execution", execution, "EXECUTES", "Workflow", row.get("workflow_id"))
            self.add_edge("Execution", execution, "PROVIDED_BY", "Cloud Provider", row.get("provider"))
            self.add_edge("Execution", execution, "RELATED_TO", "Cloud Resource", row.get("resource"))

    def _connectors(self, context: dict[str, Any]) -> None:
        for table in ("connector_registry", "connector_sync_history"):
            for row in context.get(table, []):
                connector = _first(row, "connector_name", "name", "provider", "connector_type", default="")
                provider = _first(row, "provider", "cloud_provider", "connector_type", default=connector)
                self.add_node("Connector", connector, status=_first(row, "status", "sync_status", "health"))
                self.add_edge("Connector", connector, "PROVIDED_BY", "Cloud Provider", provider)
