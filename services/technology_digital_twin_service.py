from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services import cost_intelligence_service
from services.supabase_client import supabase
from services.technology_health_service import TechnologyHealthService


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _first(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _norm(value).lower()


class TechnologyDigitalTwinService:
    """Composes the Technology Digital Twin from existing Nexora platform data."""

    def __init__(self) -> None:
        self.generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._table_cache: dict[tuple[str, int | None], list[dict[str, Any]]] = {}

    def organization_id(self) -> str:
        spend = self._table("mart_enterprise_spend_v2", limit=1)
        if spend and spend[0].get("org_id"):
            return str(spend[0]["org_id"])
        inventory = TechnologyHealthService.get_inventory()
        for row in inventory:
            if row.get("organization_id"):
                return str(row["organization_id"])
        return ""

    def technology_portfolio(self, organization_id: str | None = None) -> list[dict[str, Any]]:
        inventory = TechnologyHealthService.get_inventory()
        health_by_name = {
            _lower(row.get("Technology")): row
            for row in TechnologyHealthService.get_health_matrix()
        }
        relationships = TechnologyHealthService.get_relationships()
        applications = self._table("application_registry")
        business_services = self._table("business_services")
        spend = self._enterprise_spend()
        monthly_pool = _safe_float(spend.get("total_spend"))
        annual_total = sum(_safe_float(row.get("annual_cost")) for row in inventory)

        portfolio = []
        for index, row in enumerate(inventory):
            name = _norm(_first(row, "technology_name", "name", "application", default=f"Technology {index + 1}"))
            health_row = health_by_name.get(_lower(name), {})
            annual_cost = _safe_float(row.get("annual_cost"))
            monthly_cost = annual_cost / 12 if annual_cost else self._allocated_monthly_cost(monthly_pool, annual_total, inventory, row)
            risk_label = _norm(health_row.get("Risk") or row.get("risk") or "Low")
            health_score = _safe_float(health_row.get("Health Score") or row.get("health_score") or 100)

            portfolio.append(
                {
                    "technology_id": str(row.get("id") or name),
                    "name": name,
                    "technology_type": _first(row, "technology_type", "category", default="Technology"),
                    "vendor": _first(row, "vendor_name", "vendor", "provider", default="Unknown"),
                    "cloud_provider": _first(row, "cloud_provider", "provider", default=""),
                    "environment": _first(row, "environment", default="Production"),
                    "region": _first(row, "region", default="Global"),
                    "status": _first(row, "status", default="Active"),
                    "health": health_score,
                    "risk": self._risk_score(risk_label),
                    "risk_label": risk_label,
                    "monthly_cost": monthly_cost,
                    "annual_cost": annual_cost,
                    "owner": _first(row, "technical_owner", "business_owner", "owner_department", default="Unassigned"),
                    "applications": len(self._related_applications(name, row, applications)),
                    "business_services": len(self._related_business_services(name, row, business_services)),
                    "dependencies": len(self._relationships_for(name, relationships)),
                }
            )

        return sorted(portfolio, key=lambda item: (str(item["technology_type"]), str(item["name"]).lower()))

    def technology_context(self, organization_id: str | None, technology_id: str) -> dict[str, Any]:
        portfolio = self.technology_portfolio(organization_id)
        selected = next((item for item in portfolio if str(item.get("technology_id")) == str(technology_id)), None)
        if not selected:
            selected = portfolio[0] if portfolio else {}

        name = _norm(selected.get("name"))
        inventory_row = self._inventory_row(name)
        applications = self._related_applications(name, inventory_row, self._table("application_registry"))
        business_services = self._related_business_services(name, inventory_row, self._table("business_services"))
        relationships = self._relationships_for(name, TechnologyHealthService.get_relationships())
        recommendations = self._recommendations_for(name)
        critical_risks = self._risks_for(selected, name)
        active_incidents = self._incidents_for(name)
        resources = self._resources_for(name)

        monthly_cost = _safe_float(selected.get("monthly_cost"))
        forecast = monthly_cost * 1.12
        savings = sum(_safe_float(row.get("estimated_savings")) for row in recommendations)

        return {
            "node": selected,
            "state": {
                "health_score": selected.get("health", 0),
                "risk_score": selected.get("risk", 0),
                "status": selected.get("status", "Active"),
            },
            "applications": applications,
            "business_services": business_services,
            "relationships": relationships,
            "health": self._health_breakdown(selected),
            "infrastructure_layer": {
                "resources": resources,
                "accounts": [row for row in relationships if "account" in _lower(row.get("Target Type")) or "account" in _lower(row.get("Source Type"))],
                "regions": sorted({selected.get("region") or "Global"}),
            },
            "cost": {
                "monthly": monthly_cost,
                "annual": monthly_cost * 12,
                "forecast": forecast,
                "savings_opportunity": savings,
                "breakdown": {
                    "dimensions": {
                        "Current Monthly Spend": monthly_cost,
                        "Forecast Monthly Spend": forecast,
                        "Budget Variance": forecast - monthly_cost,
                        "Optimization Opportunity": savings,
                    }
                },
            },
            "risk": {
                "risk_score": selected.get("risk", 0),
                "risk_posture": selected.get("risk_label", "Low"),
                "breakdown": {
                    "critical_risks": critical_risks,
                    "mitigations": self._mitigations_for(selected, recommendations),
                },
            },
            "operations": {
                "operational_health": max(_safe_float(selected.get("health")) - len(active_incidents) * 3, 0),
                "incidents": len(active_incidents),
                "open_alerts": len(active_incidents),
                "deployments": len([row for row in relationships if "deploy" in _lower(row.get("Relationship"))]),
                "breakdown": {
                    "dimensions": {
                        "Open Incidents": len(active_incidents),
                        "Active Alerts": len(active_incidents),
                        "Recent Deployments": len([row for row in relationships if "deploy" in _lower(row.get("Relationship"))]),
                    },
                    "active_incidents": active_incidents,
                    "active_alerts": active_incidents,
                },
            },
            "ai": {
                "confidence": 0.86 if recommendations else 0.72,
                "confidence_band": "High" if recommendations else "Medium",
                "recommendations": recommendations,
                "predictions": self._predictions_for(selected, forecast),
                "automation_candidates": self._automation_candidates_for(selected, recommendations),
                "breakdown": {
                    "root_cause_summary": self._root_cause_summary(selected, recommendations, active_incidents),
                },
            },
            "evidence": self._evidence_for(selected, relationships, recommendations, active_incidents, resources),
            "dependency_chain": self._dependency_chain(selected, applications, business_services, relationships, resources),
        }

    def get_critical_risks(self, organization_id: str | None, technology_id: str | None = None) -> list[dict[str, Any]]:
        if technology_id:
            return self.technology_context(organization_id, technology_id).get("risk", {}).get("breakdown", {}).get("critical_risks", [])
        risks = []
        for item in self.technology_portfolio(organization_id):
            risks.extend(self._risks_for(item, _norm(item.get("name"))))
        return risks

    def get_active_incidents(self, organization_id: str | None, technology_id: str | None = None) -> list[dict[str, Any]]:
        if technology_id:
            name = _norm((self.technology_context(organization_id, technology_id).get("node") or {}).get("name"))
            return self._incidents_for(name)
        incidents = []
        for item in self.technology_portfolio(organization_id):
            incidents.extend(self._incidents_for(_norm(item.get("name"))))
        return incidents

    def get_recommendations(self, organization_id: str | None, technology_id: str | None = None) -> list[dict[str, Any]]:
        if technology_id:
            name = _norm((self.technology_context(organization_id, technology_id).get("node") or {}).get("name"))
            return self._recommendations_for(name)
        return self._recommendations_for("")

    def get_automation_candidates(self, organization_id: str | None, technology_id: str | None = None) -> list[dict[str, Any]]:
        recommendations = self.get_recommendations(organization_id, technology_id)
        return [
            row for row in recommendations
            if any(token in _lower(row.get("recommendation") or row.get("title") or row.get("description")) for token in ("rightsize", "autoscaling", "cleanup", "optimiz"))
        ]

    def graph(self, organization_id: str | None) -> dict[str, Any]:
        portfolio = self.technology_portfolio(organization_id)
        relationships = TechnologyHealthService.get_dependency_edges()
        nodes = [{"id": row["technology_id"], "label": row["name"], "type": row["technology_type"]} for row in portfolio]
        edges = [
            {
                "source": row.get("Source"),
                "relationship": row.get("Relationship"),
                "target": row.get("Target"),
            }
            for row in relationships
        ]
        return {
            "nodes": nodes,
            "infrastructure_nodes": [node for node in nodes if str(node.get("type")).lower() in {"cloud", "cloud platform"}],
            "edges": edges,
        }

    def _table(self, table_name: str, limit: int | None = None) -> list[dict[str, Any]]:
        cache_key = (table_name, limit)
        if cache_key in self._table_cache:
            return self._table_cache[cache_key]
        try:
            query = supabase.table(table_name).select("*")
            if limit:
                query = query.limit(limit)
            rows = query.execute().data or []
        except Exception:
            rows = []
        self._table_cache[cache_key] = rows
        return rows

    def _enterprise_spend(self) -> dict[str, Any]:
        rows = self._table("mart_enterprise_spend_v2", limit=1)
        return rows[0] if rows else {}

    def _inventory_row(self, name: str) -> dict[str, Any]:
        for row in TechnologyHealthService.get_inventory():
            if _lower(_first(row, "technology_name", "name")) == _lower(name):
                return row
        return {}

    def _allocated_monthly_cost(self, monthly_pool: float, annual_total: float, inventory: list[dict[str, Any]], row: dict[str, Any]) -> float:
        if not monthly_pool:
            return 0.0
        annual_cost = _safe_float(row.get("annual_cost"))
        if annual_total and annual_cost:
            return monthly_pool * (annual_cost / annual_total)
        return monthly_pool / max(len(inventory), 1)

    def _risk_score(self, risk_label: str) -> float:
        return {
            "healthy": 5,
            "low": 15,
            "medium": 45,
            "high": 75,
            "critical": 95,
        }.get(_lower(risk_label), 25)

    def _related_applications(self, name: str, row: dict[str, Any], applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
        provider = _lower(_first(row, "cloud_provider", "technology_name", "vendor_name", default=name))
        matches = []
        for app in applications:
            app_provider = _lower(_first(app, "cloud_provider", "technology_name", "vendor_name", "platform"))
            if app_provider and (app_provider in _lower(name) or app_provider in provider or provider in app_provider):
                matches.append(app)
        return matches

    def _related_business_services(self, name: str, row: dict[str, Any], services: list[dict[str, Any]]) -> list[dict[str, Any]]:
        apps = self._related_applications(name, row, self._table("application_registry"))
        units = {_lower(_first(app, "business_unit", "department")) for app in apps}
        return [
            service for service in services
            if _lower(_first(service, "business_unit", "department")) in units
        ]

    def _relationships_for(self, name: str, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
        target = _lower(name)
        rows = []
        for row in relationships:
            source = _lower(row.get("source_name") or row.get("Source"))
            related = _lower(row.get("target_name") or row.get("Target"))
            if target and (target == source or target == related or target in source or target in related):
                rows.append(
                    {
                        "Source": row.get("source_name") or row.get("Source"),
                        "Source Type": row.get("source_type") or row.get("Source Type"),
                        "Relationship": row.get("relationship_type") or row.get("Relationship"),
                        "Target": row.get("target_name") or row.get("Target"),
                        "Target Type": row.get("target_type") or row.get("Target Type"),
                    }
                )
        return rows

    def _resources_for(self, name: str) -> list[dict[str, Any]]:
        resources = [
            {
                "name": row.get("Target") or row.get("Source"),
                "resource_type": row.get("Target Type") or row.get("Source Type"),
                "provider": name,
                "region": "Global",
                "environment": "Production",
                "cost": 0,
                "health": 100,
                "risk": 0,
            }
            for row in self._relationships_for(name, TechnologyHealthService.get_dependency_edges())
            if row.get("Target") or row.get("Source")
        ]
        lower_name = _lower(name)
        derived_resources = []
        if any(provider in lower_name for provider in ("aws", "amazon")):
            services = ["EC2", "S3", "RDS", "EKS", "Lambda", "VPC", "CloudWatch"]
            derived_resources = [self._synthetic_resource(name, service, index) for index, service in enumerate(services)]
        elif "azure" in lower_name:
            services = ["Virtual Machines", "Blob Storage", "Azure SQL", "AKS", "Functions", "Virtual Network", "Monitor"]
            derived_resources = [self._synthetic_resource(name, service, index) for index, service in enumerate(services)]
        elif any(provider in lower_name for provider in ("gcp", "google cloud")):
            services = ["Compute Engine", "Cloud Storage", "Cloud SQL", "GKE", "Cloud Functions", "VPC", "Cloud Monitoring"]
            derived_resources = [self._synthetic_resource(name, service, index) for index, service in enumerate(services)]

        existing_names = {_lower(row.get("name")) for row in resources}
        for row in derived_resources:
            if _lower(row.get("name")) not in existing_names:
                resources.append(row)
        return resources

    def _synthetic_resource(self, provider: str, service: str, index: int) -> dict[str, Any]:
        return {
            "name": service,
            "resource_type": "Cloud Service",
            "provider": provider,
            "region": "Global",
            "environment": "Production",
            "cost": max(2500 - index * 260, 350),
            "health": max(96 - index * 3, 78),
            "risk": min(18 + index * 5, 55),
        }

    def _recommendations_for(self, name: str) -> list[dict[str, Any]]:
        rows = self._table("recommendations")
        if not rows:
            try:
                result = cost_intelligence_service.get_optimization_opportunities()
                rows = (result.get("data") or []).to_dict("records")
            except Exception:
                rows = []
        target = _lower(name)
        matches = []
        for row in rows:
            haystack = " ".join(str(row.get(key) or "") for key in ("service", "title", "message", "description", "recommendation_type", "owner")).lower()
            if not target or target in haystack or not matches:
                matches.append(
                    {
                        "title": row.get("title") or row.get("recommendation_type") or "Technology Recommendation",
                        "recommendation": row.get("message") or row.get("description") or "Review technology optimization opportunity.",
                        "priority": row.get("priority") or row.get("impact") or "Medium",
                        "estimated_savings": _safe_float(row.get("estimated_savings")),
                        "status": row.get("status") or "Open",
                    }
                )
        return matches[:8]

    def _risks_for(self, selected: dict[str, Any], name: str) -> list[dict[str, Any]]:
        risk_score = _safe_float(selected.get("risk"))
        health = _safe_float(selected.get("health"))
        risks = []
        if risk_score >= 40:
            risks.append(
                {
                    "Technology": selected.get("name") or name,
                    "Risk": selected.get("risk_label") or "Medium",
                    "Description": "Technology risk score indicates dependency, security, cost, or operational review is required.",
                    "Owner": selected.get("owner") or "Technology Owner",
                    "Evidence": f"Risk score {_safe_int(risk_score)}%",
                }
            )
        if health and health < 85:
            risks.append(
                {
                    "Technology": selected.get("name") or name,
                    "Risk": "Health Degradation",
                    "Description": "Health score is below the enterprise target threshold.",
                    "Owner": selected.get("owner") or "Technology Owner",
                    "Evidence": f"Health score {_safe_int(health)}%",
                }
            )
        if _safe_float(selected.get("monthly_cost")) >= 3000:
            risks.append(
                {
                    "Technology": selected.get("name") or name,
                    "Risk": "Cost Exposure",
                    "Description": "Monthly spend is material enough to require FinOps ownership and optimization review.",
                    "Owner": selected.get("owner") or "Technology Owner",
                    "Evidence": f"Monthly cost ${_safe_float(selected.get('monthly_cost')):,.0f}",
                }
            )
        return risks[:5]

    def _mitigations_for(self, selected: dict[str, Any], recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if recommendations:
            return [
                {
                    "Action": row.get("recommendation"),
                    "Priority": row.get("priority"),
                    "Owner": selected.get("owner") or "Technology Owner",
                }
                for row in recommendations[:5]
            ]
        return [
            {
                "Action": "Maintain owner, cost, risk, and relationship mappings for this technology.",
                "Priority": "Medium",
                "Owner": selected.get("owner") or "Technology Owner",
            }
        ]

    def _incidents_for(self, name: str) -> list[dict[str, Any]]:
        rows = []
        for table in ("incidents", "incident_timeline", "alerts"):
            rows.extend(self._table(table))
        target = _lower(name)
        return [
            {
                "Incident": row.get("title") or row.get("name") or row.get("incident_id") or "Operational signal",
                "Status": row.get("status") or row.get("state") or "Open",
                "Severity": row.get("severity") or row.get("priority") or "Medium",
                "Technology": name,
            }
            for row in rows
            if target in " ".join(str(value) for value in row.values()).lower()
        ][:10]

    def _health_breakdown(self, selected: dict[str, Any]) -> dict[str, Any]:
        health = _safe_float(selected.get("health"))
        risk_penalty = min(_safe_float(selected.get("risk")) / 5, 20)
        return {
            "health_score": health,
            "availability": health,
            "performance": max(health - 2, 0),
            "security": max(health - risk_penalty, 0),
            "compliance": max(health - risk_penalty * 0.8, 0),
            "cost": max(100 - min(_safe_float(selected.get("monthly_cost")) / 120, 35), 0),
            "lifecycle": max(health - 5, 0),
            "supportability": max(health - 3, 0),
            "capacity": max(health - 4, 0),
            "utilization": max(health - risk_penalty, 0),
            "reliability": max(health - 3, 0),
            "operational_score": max(health - risk_penalty / 2, 0),
        }

    def _predictions_for(self, selected: dict[str, Any], forecast: float) -> list[dict[str, Any]]:
        return [
            {
                "Prediction": "Monthly spend is projected from current technology cost baseline.",
                "Value": forecast,
                "Confidence": "Medium",
            },
            {
                "Prediction": "Health posture may degrade if open risk and dependency signals remain unresolved.",
                "Value": selected.get("health"),
                "Confidence": "Medium",
            },
        ]

    def _automation_candidates_for(self, selected: dict[str, Any], recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Candidate": row.get("title"),
                "Action": row.get("recommendation"),
                "Owner": selected.get("owner") or "Technology Owner",
            }
            for row in recommendations
            if row.get("recommendation")
        ][:5]

    def _root_cause_summary(self, selected: dict[str, Any], recommendations: list[dict[str, Any]], incidents: list[dict[str, Any]]) -> str:
        return (
            f"{selected.get('name', 'This technology')} has health score {selected.get('health', 0):.1f}, "
            f"risk posture {selected.get('risk_label', 'Low')}, {len(incidents)} active incident signals, "
            f"and {len(recommendations)} AI or optimization recommendations."
        )

    def _dependency_chain(
        self,
        selected: dict[str, Any],
        applications: list[dict[str, Any]],
        business_services: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        resources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        technology_name = selected.get("name") or "Technology"
        service_name = _first(business_services[0], "service_name", "name", default="Business Service") if business_services else "Business Service"
        application_name = _first(applications[0], "application_name", "name", default="Application") if applications else "Application"
        resource_name = resources[0].get("name") if resources else "Resource"
        cost_label = f"${_safe_float(selected.get('monthly_cost')):,.0f} monthly cost"
        risk_label = f"{selected.get('risk_label') or 'Low'} risk"
        return [
            {"Layer": "Business Service", "Node": service_name, "Relationship": "depends on"},
            {"Layer": "Application", "Node": application_name, "Relationship": "runs on"},
            {"Layer": "Technology", "Node": technology_name, "Relationship": "uses"},
            {"Layer": "Infrastructure", "Node": resource_name, "Relationship": "generates"},
            {"Layer": "Cost", "Node": cost_label, "Relationship": "informs"},
            {"Layer": "Risk", "Node": risk_label, "Relationship": "requires governance"},
        ]

    def _evidence_for(
        self,
        selected: dict[str, Any],
        relationships: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
        resources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence = [
            {
                "Signal": "Technology inventory",
                "Source": "technology_inventory",
                "Finding": f"{selected.get('name')} owner is {selected.get('owner') or 'Unassigned'}",
                "Confidence": "High",
            },
            {
                "Signal": "Health matrix",
                "Source": "technology_health_service",
                "Finding": f"Health {_safe_int(selected.get('health'))}% and risk {_safe_int(selected.get('risk'))}%",
                "Confidence": "High",
            },
            {
                "Signal": "Cost baseline",
                "Source": "mart_enterprise_spend_v2 / inventory allocation",
                "Finding": f"Monthly technology cost ${_safe_float(selected.get('monthly_cost')):,.0f}",
                "Confidence": "Medium",
            },
        ]
        if relationships:
            evidence.append(
                {
                    "Signal": "Dependency",
                    "Source": "technology_relationships",
                    "Finding": f"{len(relationships)} dependency relationships mapped",
                    "Confidence": "High",
                }
            )
        if resources:
            evidence.append(
                {
                    "Signal": "Infrastructure layer",
                    "Source": "technology_relationships / derived cloud services",
                    "Finding": f"{len(resources)} infrastructure resources or cloud services mapped",
                    "Confidence": "Medium",
                }
            )
        if recommendations:
            evidence.append(
                {
                    "Signal": "AI recommendation",
                    "Source": "recommendations / cost intelligence",
                    "Finding": recommendations[0].get("recommendation") or recommendations[0].get("title"),
                    "Confidence": "Medium",
                }
            )
        if incidents:
            evidence.append(
                {
                    "Signal": "Operational signal",
                    "Source": "incidents / alerts",
                    "Finding": f"{len(incidents)} active incident or alert signals linked",
                    "Confidence": "Medium",
                }
            )
        return evidence
