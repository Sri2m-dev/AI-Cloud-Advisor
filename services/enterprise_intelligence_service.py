from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services import audit_service
from services.enterprise_graph_service import EnterpriseGraphService


INTELLIGENCE_WORKSPACE = [
    {"Label": "Knowledge Graph", "Path": "pages/enterprise_graph.py"},
    {"Label": "Dependency Analysis", "Path": "pages/dependency_analysis.py"},
    {"Label": "Impact Analysis", "Path": "pages/impact_analysis.py"},
    {"Label": "Simulation Center", "Path": "pages/simulation_center.py"},
    {"Label": "AI Reasoning Center", "Path": "pages/ai_reasoning.py"},
]

DEMO_SCENARIOS = [
    {
        "Name": "AWS outage",
        "Asset": "AWS",
        "Scenario Type": "Cloud",
        "Scenario": "Region outage",
        "Question": "What happens if AWS US-East-1 goes down?",
    },
    {
        "Name": "Oracle migration",
        "Asset": "Oracle",
        "Scenario Type": "Database",
        "Scenario": "Migrate",
        "Question": "Can we migrate Oracle to PostgreSQL?",
    },
    {
        "Name": "SaaS license reduction",
        "Asset": "Microsoft 365",
        "Scenario Type": "SaaS",
        "Scenario": "Remove licenses",
        "Question": "What if I reduce Microsoft 365 licenses by 15%?",
    },
    {
        "Name": "Datadog replacement",
        "Asset": "Datadog",
        "Scenario Type": "Applications",
        "Scenario": "Decommission",
        "Question": "Can we remove Datadog and move to CloudWatch?",
    },
]


class EnterpriseIntelligenceService:
    @staticmethod
    def get_workspace_pages() -> list[dict[str, str]]:
        return INTELLIGENCE_WORKSPACE

    @staticmethod
    def get_demo_scenarios() -> list[dict[str, str]]:
        return DEMO_SCENARIOS

    @staticmethod
    def get_assets(organization_id: str | None = None) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        return EnterpriseIntelligenceService._cached_assets(org_id)

    @staticmethod
    @lru_cache(maxsize=16)
    def _cached_assets(org_id: str) -> list[dict[str, Any]]:
        graph = EnterpriseGraphService.build_graph(org_id)
        preferred_types = {
            "Technology",
            "Cloud Provider",
            "Application",
            "Business Service",
            "Business Capability",
            "Enterprise Asset",
            "Cloud Resource",
            "Department",
            "Owner",
        }
        assets = [
            {
                "name": node["name"],
                "type": node["type"],
                "label": f"{node['name']} ({node['type']})",
            }
            for node in graph["nodes"]
            if node["type"] in preferred_types
        ]
        return sorted(assets, key=lambda row: (row["type"], row["name"]))

    @staticmethod
    def standard_explanation(
        recommendation: str,
        why: str,
        evidence: list[Any] | None = None,
        policies: list[Any] | None = None,
        alternatives: list[Any] | None = None,
        confidence: Any = None,
        risks: Any = None,
        expected_outcome: str | None = None,
    ) -> dict[str, Any]:
        return {
            "Recommendation": recommendation,
            "Why": why,
            "Evidence": evidence or [],
            "Policies Applied": policies or [],
            "Alternatives": alternatives or [],
            "Confidence": confidence,
            "Risks": risks,
            "Expected Outcome": expected_outcome,
            "Generated At": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def log_intelligence_event(
        event_type: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        organization_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            audit_service.log_event(
                event_type=event_type,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                org_id=organization_id,
                details=details or {},
            )
        except Exception:
            pass
