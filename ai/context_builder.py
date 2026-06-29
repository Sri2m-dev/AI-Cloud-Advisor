from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.ai_context_service import AIContextService
from services.enterprise_graph_service import EnterpriseGraphService
from services.impact_analysis_service import ImpactAnalysisService
from services.simulation_service import SimulationService


def build_reasoning_context(
    question: str,
    organization_id: str | None = None,
    scenario_type: str | None = None,
    scenario: str | None = None,
) -> dict[str, Any]:
    org_id = resolve_organization_id(organization_id)
    asset = extract_asset(question, org_id)
    context = {
        "organization_id": org_id,
        "question": question,
        "asset": asset,
        "enterprise": AIContextService.build_enterprise_context(org_id),
    }
    if asset:
        context["impact"] = ImpactAnalysisService.analyze_asset(
            asset,
            organization_id=org_id,
            use_cache=False,
        )
    resolved_scenario = scenario or infer_scenario(question)
    resolved_type = scenario_type or infer_scenario_type(question)
    if asset and resolved_scenario:
        context["simulation"] = SimulationService.run_simulation(
            asset=asset,
            scenario_type=resolved_type,
            scenario=resolved_scenario,
            organization_id=org_id,
            simulation_mode="Reasoning",
            created_by="ai_reasoning",
            persist=False,
        )
    return context


def extract_asset(question: str, organization_id: str | None = None) -> str | None:
    text = str(question or "").lower()
    known_assets = {
        "microsoft 365": "Microsoft 365",
        "cloudwatch": "CloudWatch",
        "postgresql": "PostgreSQL",
        "oracle": "Oracle",
        "datadog": "Datadog",
        "azure": "Azure",
        "aws": "AWS",
        "arm": "ARM",
    }
    for token, label in known_assets.items():
        if token in text:
            return label
    try:
        graph = EnterpriseGraphService.build_graph(resolve_organization_id(organization_id))
        candidates = sorted(
            {
                node["name"]
                for node in graph["nodes"]
                if node["type"] in {
                    "Technology",
                    "Cloud Provider",
                    "Application",
                    "Business Service",
                    "Enterprise Asset",
                    "Cloud Resource",
                }
            },
            key=len,
            reverse=True,
        )
        for name in candidates:
            lowered = name.lower()
            if lowered in text or lowered.replace(" enterprise", "") in text:
                return name
    except Exception:
        return None
    return None


def infer_scenario(question: str) -> str:
    text = str(question or "").lower()
    if "postgres" in text or "migrate" in text:
        return "Migrate"
    if "decommission" in text or "remove" in text:
        return "Decommission"
    if "arm" in text:
        return "Migration"
    if "stop" in text or "server" in text or "vm" in text:
        return "Stop VM"
    if "outage" in text or "goes down" in text or "unavailable" in text:
        return "Region outage"
    if "safest optimization" in text or "optimization" in text:
        return "Resize VM"
    return "Migration"


def infer_scenario_type(question: str) -> str:
    text = str(question or "").lower()
    if "postgres" in text or "database" in text or "oracle" in text:
        return "Database"
    if "license" in text or "microsoft 365" in text:
        return "SaaS"
    if "cost" in text or "budget" in text:
        return "Financial"
    if "stop" in text or "server" in text or "vm" in text:
        return "Infrastructure"
    if "outage" in text or "region" in text or "cloud" in text:
        return "Cloud"
    return "Applications"
