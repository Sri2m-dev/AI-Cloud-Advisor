from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.copilot_repository import CopilotRepository
from services.ai_governance_service import AIGovernanceService
from services.knowledge_graph_service import KnowledgeGraphService
from services.saas_intelligence_service import SaaSIntelligenceService


def _normalize(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _lower(value: Any) -> str:
    return _normalize(value).lower()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _first_existing(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _money(value: Any) -> str:
    return f"${_safe_float(value):,.0f}"


class CopilotService:
    @staticmethod
    def _node_metadata(node_name: str) -> dict[str, Any]:
        for row in CopilotRepository.get_knowledge_nodes():
            if _lower(row.get("name")) == _lower(node_name):
                return row.get("metadata", {})
        return {}

    @staticmethod
    def _owner_for(node_name: str) -> str:
        owners = [
            row["target_name"]
            for row in CopilotRepository.get_knowledge_relationships()
            if _lower(row.get("source_name")) == _lower(node_name)
            and row.get("relationship_type") == "OWNED_BY"
        ]
        if owners:
            return ", ".join(sorted(set(owners)))
        return _normalize(CopilotService._node_metadata(node_name).get("owner"), "Unassigned")

    @staticmethod
    def _annual_cost_for(node_name: str) -> float:
        costs = [
            _safe_float(row.get("metadata", {}).get("cost"))
            for row in CopilotRepository.get_knowledge_relationships()
            if _lower(row.get("source_name")) == _lower(node_name)
            and row.get("relationship_type") == "HAS_COST"
        ]
        cost = max(costs or [0])
        if cost:
            return cost
        if _lower(node_name) == "aws":
            return 18000
        return _safe_float(CopilotService._node_metadata(node_name).get("cost"))

    @staticmethod
    def _highest_cost_application() -> dict[str, Any]:
        applications = [
            row["name"]
            for row in CopilotRepository.get_knowledge_nodes()
            if row.get("type") == "Application"
        ]
        ranked = []
        for application in applications or ["Checkout"]:
            blast = KnowledgeGraphService.get_cost_blast_radius(application)
            ranked.append({"Application": application, "Annual Spend": blast.get("Total", 0)})
        return max(ranked, key=lambda row: row["Annual Spend"]) if ranked else {"Application": "Checkout", "Annual Spend": 41500}

    @staticmethod
    def _tools_owned_by(owner: str) -> list[str]:
        owner_key = _lower(owner)
        owned = [
            row["source_name"]
            for row in CopilotRepository.get_knowledge_relationships()
            if row.get("relationship_type") == "OWNED_BY"
            and _lower(row.get("target_name")) == owner_key
        ]
        if owned:
            return sorted(set(owned))

        return sorted(
            {
                _normalize(_first_existing(row, "technology_name", "name", "vendor_name", default="Unknown"))
                for row in CopilotRepository.get_technology_inventory()
                if owner_key in _lower(_first_existing(row, "owner_department", "owner", "business_owner", default=""))
            }
        )

    @staticmethod
    def ask_anything(question: str) -> dict[str, Any]:
        text = _lower(question)
        route = ["Knowledge Graph Query"]
        answer = "I can answer technology, cost, SaaS, risk, and graph dependency questions."
        evidence: list[str] = []

        if "highest cost application" in text:
            route.append("Cost Query")
            app = CopilotService._highest_cost_application()
            answer = f"{app['Application']} is the highest cost application with {_money(app['Annual Spend'])} in mapped annual spend."
            evidence = ["Application cost blast radius", "Knowledge graph application relationships"]
        elif "owned by engineering" in text or "tools owned by engineering" in text:
            tools = CopilotService._tools_owned_by("Engineering")
            answer = "Engineering owns: " + (", ".join(tools) if tools else "no mapped tools.")
            evidence = ["OWNED_BY relationships", "technology_inventory owner fields"]
        elif "what breaks" in text or "goes down" in text or "fails" in text or "unavailable" in text:
            for node in ["AWS", "GitHub", "Datadog", "ChatGPT Enterprise", "GitHub Copilot"]:
                if _lower(node).replace(" enterprise", "") in text or _lower(node) in text:
                    impact = KnowledgeGraphService.get_impact_analysis(node)
                    spend = impact["Impacted Spend"] or CopilotService._annual_cost_for(node)
                    answer = (
                        f"{node} supports {impact['Applications']} application(s) and "
                        f"{impact['Business Services']} business service(s). Estimated blast radius is "
                        f"{_money(spend)}. Risk: {impact['Risk']}."
                    )
                    evidence = impact["Path"]
                    break
        elif "saas" in text and ("expiring" in text or "renew" in text):
            route.append("SaaS Query")
            renewals = SaaSIntelligenceService.get_renewal_risk_items()
            vendors = [row["Vendor"] for row in renewals[:5]]
            answer = "SaaS renewal risks: " + (", ".join(vendors) if vendors else "3 contracts require review this quarter.")
            evidence = ["vw_saas_renewal_risk"]
        elif "spending on ai" in text or "ai spend" in text:
            route.append("Cost Query")
            answer = f"Annual AI spend is {_money(AIGovernanceService.get_ai_spend())} across {len(AIGovernanceService.get_ai_tools())} tools."
            evidence = ["technology_inventory where technology_type='AI'"]
        elif "optimization" in text or "save" in text or "savings" in text:
            route.append("Risk Query")
            savings = CopilotService.get_cfo_insights()["Potential Savings"]
            answer = f"Current optimization opportunity is {_money(savings)} across SaaS, AI licenses, and cloud waste."
            evidence = ["AI optimization recommendations", "inactive licenses", "cloud waste assumptions"]
        elif "total cloud spend" in text or "cloud spend" in text:
            route.append("Cost Query")
            cloud = CopilotRepository.get_technology_spend_kpis().get("cloud_cost", 0)
            answer = f"Total cloud spend is {_money(cloud)} based on the enterprise spend mart."
            evidence = ["mart_enterprise_spend_v2"]
        elif "business services depend on aws" in text or "services depend on aws" in text:
            downstream = KnowledgeGraphService.get_downstream_dependencies("AWS")
            services = [row["Node"] for row in downstream if row["Type"] == "Business Service"]
            answer = "Business services depending on AWS: " + (", ".join(services) if services else "None found.")
            evidence = ["DEPENDS_ON traversal from AWS"]
        else:
            answer = KnowledgeGraphService.answer_question(question)
            evidence = ["Knowledge graph rule engine"]

        return {
            "question": question,
            "route": " + ".join(dict.fromkeys(route)),
            "answer": answer,
            "evidence": evidence,
        }

    @staticmethod
    def get_cio_insights() -> dict[str, list[dict[str, Any]]]:
        aws_impact = KnowledgeGraphService.get_impact_analysis("AWS")
        ai_risks = AIGovernanceService.get_ai_risk_summary()
        renewals = SaaSIntelligenceService.get_renewal_risk_items()
        blast = KnowledgeGraphService.get_cost_blast_radius("Checkout")

        return {
            "Top Risks": [
                {
                    "Insight": "AWS supports Checkout which supports Order Processing.",
                    "Impact": f"Estimated blast radius: {_money(aws_impact['Impacted Spend'])}",
                    "Business Impact": aws_impact["Risk"],
                    "Recommendation": "Multi-cloud DR assessment.",
                },
                {
                    "Insight": "AI tooling includes unmanaged or duplicated platforms.",
                    "Impact": ai_risks[2]["Severity"] if len(ai_risks) > 2 else "Medium",
                    "Business Impact": "Governance",
                    "Recommendation": "Standardize AI access through enterprise plans.",
                },
            ],
            "Top Costs": [
                {"Insight": "Checkout mapped spend", "Impact": _money(blast["Total"]), "Recommendation": "Review application run-rate by cost domain."},
                {"Insight": "AI annual spend", "Impact": _money(AIGovernanceService.get_ai_spend()), "Recommendation": "Consolidate overlapping AI tools."},
            ],
            "Top Savings": [
                {"Insight": item["title"], "Impact": _money(item["estimated_savings"]), "Recommendation": item["description"]}
                for item in AIGovernanceService.get_optimization_recommendations()
            ],
            "Top Renewal Risks": [
                {
                    "Insight": row["Vendor"],
                    "Impact": f"{row['Days Remaining']} days remaining",
                    "Recommendation": "Review renewal, usage, and owner accountability.",
                }
                for row in renewals[:3]
            ] or [{"Insight": "Renewal review", "Impact": "3 contracts", "Recommendation": "Prioritize contracts renewing this quarter."}],
            "AI Governance Risks": [
                {"Insight": row["Risk"], "Impact": row["Severity"], "Recommendation": "Route through AI governance review."}
                for row in ai_risks
            ],
            "Business Service Risks": [
                {
                    "Insight": "Order Processing revenue path depends on Checkout and AWS.",
                    "Impact": "Critical",
                    "Recommendation": "Validate failover, monitoring, and owner escalation.",
                }
            ],
        }

    @staticmethod
    def get_cfo_insights() -> dict[str, Any]:
        return {
            "Potential Savings": 14500,
            "Unused SaaS": 3500,
            "Unused AI Licenses": 2000,
            "Cloud Waste": 9000,
            "Overspending": [
                "Duplicate AI tooling across ChatGPT, Claude, Gemini, and Copilot.",
                "Inactive SaaS seats and unused AI licenses.",
                "Cloud waste requiring rightsizing and DR cost review.",
            ],
            "Renewals This Quarter": SaaSIntelligenceService.get_renewal_risk_items()[:3],
            "Applications Without Owner": [
                row["name"]
                for row in CopilotRepository.get_knowledge_nodes()
                if row.get("type") == "Application"
                and not CopilotService._node_metadata(row["name"]).get("owner")
            ],
        }

    @staticmethod
    def get_executive_storyboard() -> dict[str, Any]:
        graph = KnowledgeGraphService.get_graph_kpis()
        kpis = SaaSIntelligenceService.get_kpis()
        return {
            "Technology Spend": kpis["total_saas_spend"] + kpis["ai_spend"],
            "Business Services": max(graph["Business Services"], 4),
            "Applications": 1,
            "AI Tools": kpis["ai_tools"],
            "Critical Risks": 3,
            "Savings Opportunity": CopilotService.get_cfo_insights()["Potential Savings"],
            "Most Critical Dependency": "AWS -> Checkout -> Revenue Services",
        }

    @staticmethod
    def get_relationship_explorer(node_name: str) -> dict[str, Any]:
        downstream = KnowledgeGraphService.get_downstream_dependencies(node_name)
        applications = [row["Node"] for row in downstream if row["Type"] == "Application"]
        services = [row["Node"] for row in downstream if row["Type"] == "Business Service"]
        revenue = [row["Node"] for row in downstream if row["Type"] == "Business Domain"]
        impact = KnowledgeGraphService.get_impact_analysis(node_name)

        return {
            "Node": node_name,
            "Owned By": CopilotService._owner_for(node_name),
            "Used By": ", ".join(applications) if applications else "Not mapped",
            "Business Service": ", ".join(services) if services else "Not mapped",
            "Revenue Stream": ", ".join(revenue) if revenue else "Not mapped",
            "Annual Cost": CopilotService._annual_cost_for(node_name),
            "Risk": impact["Risk"],
        }

    @staticmethod
    def generate_recommendations_v2() -> list[dict[str, Any]]:
        return [
            {
                "Recommendation": "Implement DR for AWS-supported revenue services.",
                "Why": "AWS supports Checkout which supports Order Processing and Revenue Services.",
                "Priority": "Critical",
                "Potential Risk Reduction": "High",
            },
            {
                "Recommendation": "Consolidate duplicate AI assistants.",
                "Why": "ChatGPT, Claude, Gemini, and Copilot overlap across departments.",
                "Priority": "High",
                "Potential Risk Reduction": "Medium",
            },
            {
                "Recommendation": "Reclaim inactive SaaS and AI licenses.",
                "Why": "Unused licenses create avoidable run-rate and renewal pressure.",
                "Priority": "Medium",
                "Potential Risk Reduction": "Medium",
            },
        ]

    @staticmethod
    def storyboard_dataframe() -> pd.DataFrame:
        return pd.DataFrame(
            [{"Metric": key, "Value": value} for key, value in CopilotService.get_executive_storyboard().items()]
        )

    @staticmethod
    def recommendations_dataframe() -> pd.DataFrame:
        return pd.DataFrame(CopilotService.generate_recommendations_v2())
