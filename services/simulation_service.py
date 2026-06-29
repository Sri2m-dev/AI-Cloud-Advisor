from __future__ import annotations

import uuid
from datetime import datetime
from io import BytesIO
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from graph.simulation_risk import calculate_simulation_risk
from repositories.simulation_repository import SimulationRepository
from services.enterprise_graph_service import EnterpriseGraphService
from services.enterprise_intelligence_service import EnterpriseIntelligenceService
from services.impact_analysis_service import ImpactAnalysisService, _minimal_pptx, _minimal_xlsx

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except ImportError:  # pragma: no cover
    letter = None
    canvas = None


SCENARIO_CATALOG = {
    "Infrastructure": ["Stop VM", "Delete VM", "Resize VM", "Restart VM"],
    "Cloud": ["Delete VPC", "Remove Load Balancer", "Region outage", "Availability Zone outage", "Storage failure"],
    "Database": ["Upgrade", "Migrate", "Decommission", "Failover", "Backup restore"],
    "SaaS": ["Remove licenses", "Replace vendor", "Consolidate tools", "Change subscription tier"],
    "Applications": ["Decommission", "Migration", "DR failover", "Upgrade", "Scaling"],
    "Financial": ["Budget reduction", "20% spend increase", "Vendor price increase", "Reserved Instance purchase", "Savings Plan adoption"],
}


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _money(value: Any) -> str:
    return f"${_safe_float(value):,.0f}"


class SimulationService:
    @staticmethod
    def get_scenario_catalog() -> dict[str, list[str]]:
        return SCENARIO_CATALOG

    @staticmethod
    def run_simulation(
        asset: str,
        scenario_type: str,
        scenario: str,
        organization_id: str | None = None,
        environment: str = "Production",
        simulation_mode: str = "Executive Decision",
        simulation_date: str | None = None,
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        impact = ImpactAnalysisService.analyze_asset(asset, organization_id=org_id, use_cache=False)
        context = SimulationRepository.load_context(org_id)
        assumptions = SimulationService._scenario_assumptions(scenario_type, scenario, impact, context)
        financial = SimulationService._financial_analysis(impact, assumptions)
        risk = SimulationService._risk_analysis(impact, assumptions, financial)
        approvals = SimulationService._approval_analysis(impact, risk, financial)
        technical = SimulationService._technical_impact(impact, assumptions)
        business = SimulationService._business_impact(impact, assumptions, financial)
        recommendation = SimulationService._ai_recommendation(
            asset=impact["asset"],
            scenario=scenario,
            risk=risk,
            business=business,
            financial=financial,
            approvals=approvals,
            assumptions=assumptions,
        )
        status = SimulationService._status_from_recommendation(recommendation)

        result = {
            "id": run_id,
            "organization_id": org_id,
            "simulation_name": f"{scenario} - {impact['asset']}",
            "asset_id": impact["asset"],
            "asset_type": impact["asset_type"],
            "scenario_type": scenario_type,
            "scenario": scenario,
            "environment": environment,
            "simulation_mode": simulation_mode,
            "simulation_date": simulation_date or now[:10],
            "status": status,
            "created_by": created_by,
            "created_at": now,
            "impact_analysis": impact,
            "technical_impact": technical,
            "business_impact": business,
            "financial_analysis": financial,
            "risk_analysis": risk,
            "approval_analysis": approvals,
            "ai_recommendation": recommendation,
            "explanation": EnterpriseIntelligenceService.standard_explanation(
                recommendation=recommendation["Recommendation"],
                why=recommendation["AI Summary"],
                evidence=[
                    f"Applications impacted: {business['Applications Impacted']}",
                    f"Business services: {business['Business Services']}",
                    f"Revenue exposure/day: {_money(financial['Revenue Exposure Per Day'])}",
                    f"Expected annual savings: {_money(financial['Expected Annual Savings'])}",
                    f"Risk: {risk['level']}",
                ],
                policies=[row["Approver Role"] for row in approvals if row.get("Required") == "Yes"],
                alternatives=[recommendation["Alternative"]],
                confidence=recommendation["Confidence"],
                risks=risk["level"],
                expected_outcome=SimulationService._executive_summary(
                    impact["asset"],
                    scenario,
                    business,
                    financial,
                    risk,
                    recommendation,
                ),
            ),
            "assumptions": assumptions,
            "executive_summary": SimulationService._executive_summary(
                impact["asset"],
                scenario,
                business,
                financial,
                risk,
                recommendation,
            ),
        }
        if persist:
            SimulationService._persist(result)
        return result

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        runs = SimulationRepository.list_runs(org_id)
        results = SimulationRepository.list_results(org_id)
        active = [row for row in runs if str(row.get("status") or "").lower() in {"draft", "running", "review", "approved"}]
        high_risk = [row for row in results if _safe_float(row.get("risk_score")) >= 70]
        approved = [row for row in runs if str(row.get("status") or "").lower() == "approved"]
        rejected = [row for row in runs if str(row.get("status") or "").lower() == "rejected"]
        confidence = [_safe_float(row.get("confidence")) for row in results if row.get("confidence") is not None]
        savings = 0.0
        for row in runs:
            simulation_results = row.get("simulation_results") or {}
            if isinstance(simulation_results, dict):
                savings += _safe_float(
                    (simulation_results.get("financial_analysis") or {}).get("Expected Annual Savings")
                )
        graph = EnterpriseGraphService.build_graph(org_id)
        return {
            "kpis": {
                "Active Simulations": len(active),
                "Potential Savings": savings,
                "High Risk Scenarios": len(high_risk),
                "Approved Simulations": len(approved),
                "Rejected Simulations": len(rejected),
                "Average Confidence": round(sum(confidence) / len(confidence), 1) if confidence else 0.0,
            },
            "runs": runs,
            "results": results,
            "assets": sorted(
                [
                    {"name": node["name"], "type": node["type"]}
                    for node in graph["nodes"]
                    if node["type"] in {
                        "Technology",
                        "Cloud Provider",
                        "Application",
                        "Business Service",
                        "Enterprise Asset",
                        "Cloud Resource",
                    }
                ],
                key=lambda row: (row["type"], row["name"]),
            ),
            "scenario_catalog": SCENARIO_CATALOG,
        }

    @staticmethod
    def build_pdf(simulation: dict[str, Any]) -> bytes:
        if canvas is None or letter is None:
            raise RuntimeError("PDF export requires reportlab.")
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle(simulation["simulation_name"])
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, 760, f"Nexora - Simulation: {simulation['simulation_name']}")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, 742, f"Generated: {simulation['created_at'][:19]} UTC")
        y = 710
        for title, lines in SimulationService._report_sections(simulation):
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(40, y, title)
            y -= 16
            pdf.setFont("Helvetica", 9)
            for line in lines:
                pdf.drawString(52, y, str(line)[:110])
                y -= 13
                if y < 70:
                    pdf.showPage()
                    y = 760
            y -= 8
        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def build_excel(simulation: dict[str, Any]) -> bytes:
        sheets = {
            "Summary": [SimulationService._summary_row(simulation)],
            "Financial": [simulation["financial_analysis"]],
            "Risk": [simulation["risk_analysis"]["summary"]],
            "Risk Breakdown": simulation["risk_analysis"]["breakdown"],
            "Approvals": simulation["approval_analysis"],
            "Technical": [simulation["technical_impact"]],
            "Business": [simulation["business_impact"]],
            "Assumptions": [{"Assumption": key, "Value": value} for key, value in simulation["assumptions"].items()],
        }
        return _minimal_xlsx(sheets)

    @staticmethod
    def build_powerpoint(simulation: dict[str, Any]) -> bytes:
        slides = [
            (
                simulation["simulation_name"],
                [
                    simulation["executive_summary"],
                    f"Recommendation: {simulation['ai_recommendation']['Recommendation']}",
                    f"Confidence: {simulation['ai_recommendation']['Confidence']}%",
                ],
            ),
            ("Business Impact", [f"{key}: {value}" for key, value in simulation["business_impact"].items()]),
            ("Financial Analysis", [f"{key}: {value}" for key, value in simulation["financial_analysis"].items()]),
            ("Risk And Approvals", [f"{key}: {value}" for key, value in simulation["risk_analysis"]["summary"].items()] + [f"{row['Approver Role']}: {row['Status']}" for row in simulation["approval_analysis"]]),
            ("AI Recommendation", [simulation["ai_recommendation"]["AI Summary"], simulation["ai_recommendation"]["Alternative"]]),
        ]
        return _minimal_pptx(slides)

    @staticmethod
    def _scenario_assumptions(
        scenario_type: str,
        scenario: str,
        impact: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del context
        scenario_key = f"{scenario_type} {scenario}".lower()
        annual_cost = _safe_float(impact["financial_impact"]["Annual Cost"])
        revenue_day = _safe_float(impact["financial_impact"].get("Estimated Revenue Risk Per Day"))
        assumptions = {
            "Availability Impact %": 35,
            "Cost Change %": -10,
            "Migration Cost": max(annual_cost * 0.08, 5000),
            "Rollback Available": "Yes",
            "Failover Ready %": 72,
            "Duration Weeks": 4,
            "Revenue Exposure Per Day": revenue_day,
            "Confidence": 92,
        }
        if any(token in scenario_key for token in ["delete", "decommission", "outage", "failure", "stop"]):
            assumptions.update({"Availability Impact %": 85, "Cost Change %": -18, "Rollback Available": "Conditional", "Confidence": 96})
        if any(token in scenario_key for token in ["resize", "reserved", "savings plan", "remove licenses", "consolidate", "subscription"]):
            assumptions.update({"Availability Impact %": 25, "Cost Change %": -22, "Migration Cost": max(annual_cost * 0.03, 2500), "Rollback Available": "Yes", "Confidence": 94})
        if any(token in scenario_key for token in ["migrate", "upgrade", "postgresql", "replace vendor"]):
            assumptions.update({"Availability Impact %": 45, "Cost Change %": -28, "Migration Cost": max(annual_cost * 0.18, 25000), "Duration Weeks": 18, "Confidence": 91})
        if any(token in scenario_key for token in ["20% spend increase", "price increase"]):
            assumptions.update({"Availability Impact %": 10, "Cost Change %": 20, "Migration Cost": 0, "Rollback Available": "No", "Confidence": 93})
        if "budget reduction" in scenario_key:
            assumptions.update({"Availability Impact %": 50, "Cost Change %": -15, "Migration Cost": max(annual_cost * 0.05, 5000), "Confidence": 89})
        return assumptions

    @staticmethod
    def _financial_analysis(impact: dict[str, Any], assumptions: dict[str, Any]) -> dict[str, Any]:
        current_annual = _safe_float(impact["financial_impact"]["Annual Cost"])
        cost_change = _safe_float(assumptions["Cost Change %"]) / 100
        projected_annual = max(current_annual * (1 + cost_change), 0)
        annual_savings = current_annual - projected_annual
        monthly_savings = annual_savings / 12
        migration_cost = _safe_float(assumptions["Migration Cost"])
        roi = (annual_savings / migration_cost * 100) if migration_cost and annual_savings > 0 else 0
        payback = (migration_cost / max(monthly_savings, 1)) if monthly_savings > 0 else 0
        return {
            "Current Annual Cost": round(current_annual, 2),
            "Projected Annual Cost": round(projected_annual, 2),
            "Expected Annual Savings": round(annual_savings, 2),
            "Expected Monthly Savings": round(monthly_savings, 2),
            "Migration Cost": round(migration_cost, 2),
            "ROI %": round(roi, 1),
            "Payback Months": round(payback, 1),
            "Budget Impact": round(projected_annual - current_annual, 2),
            "Revenue Exposure Per Day": round(_safe_float(assumptions["Revenue Exposure Per Day"]), 2),
        }

    @staticmethod
    def _risk_analysis(
        impact: dict[str, Any],
        assumptions: dict[str, Any],
        financial: dict[str, Any],
    ) -> dict[str, Any]:
        impact_risk = _safe_float(impact["risk_score"])
        availability = _safe_float(assumptions["Availability Impact %"])
        revenue = _safe_float(financial["Revenue Exposure Per Day"])
        factors = {
            "technical": min(impact_risk * 0.55 + availability * 0.45, 100),
            "business": min(_safe_float(impact["impact_score"]) * 0.65 + availability * 0.35, 100),
            "financial": min(abs(_safe_float(financial["Budget Impact"])) / max(_safe_float(financial["Current Annual Cost"]), 1) * 100 + (35 if revenue else 0), 100),
            "security": _safe_float((impact.get("score_components") or {}).get("security_risk")),
            "compliance": _safe_float(impact["risk_analysis"].get("Compliance Risk")),
            "customer_impact": min(_safe_float(impact["business_impact"]["Customers"]) / 150000 * 100, 100),
            "operational": _safe_float(impact["risk_analysis"].get("Operational Risk")),
        }
        calculated = calculate_simulation_risk(factors)
        return {
            "summary": {
                "Risk Score": calculated["risk_score"],
                "Risk": calculated["risk_level"],
                "Rollback": assumptions["Rollback Available"],
                "Failover Ready": f"{assumptions['Failover Ready %']}%",
                "Confidence": assumptions["Confidence"],
            },
            "breakdown": [
                {
                    "Category": key.replace("_", " ").title(),
                    "Score": value,
                    "Weight": round(calculated["weights"][key] * 100, 0),
                }
                for key, value in calculated["breakdown"].items()
            ],
            "score": calculated["risk_score"],
            "level": calculated["risk_level"],
        }

    @staticmethod
    def _approval_analysis(
        impact: dict[str, Any],
        risk: dict[str, Any],
        financial: dict[str, Any],
    ) -> list[dict[str, Any]]:
        approvals = list(impact.get("approval_intelligence") or [])
        if risk["score"] >= 70 and not any(row.get("Approver Role") == "CIO" for row in approvals):
            approvals.insert(
                0,
                {
                    "Approver Role": "CIO",
                    "Approver": "CIO",
                    "Required": "Yes",
                    "Reason": "High-risk enterprise simulation",
                    "Status": "Required",
                },
            )
        if abs(_safe_float(financial["Budget Impact"])) >= 100000 and not any(row.get("Approver Role") == "Finance" for row in approvals):
            approvals.append(
                {
                    "Approver Role": "Finance",
                    "Approver": "Finance",
                    "Required": "Yes",
                    "Reason": "Material budget impact",
                    "Status": "Required",
                }
            )
        return approvals[:8]

    @staticmethod
    def _technical_impact(impact: dict[str, Any], assumptions: dict[str, Any]) -> dict[str, Any]:
        return {
            "Assets Impacted": len(impact.get("impacted_nodes", [])),
            "Applications Impacted": impact["business_impact"]["Applications Impacted"],
            "Availability Impact": f"{assumptions['Availability Impact %']}%",
            "Rollback": assumptions["Rollback Available"],
            "Failover Ready": f"{assumptions['Failover Ready %']}%",
        }

    @staticmethod
    def _business_impact(
        impact: dict[str, Any],
        assumptions: dict[str, Any],
        financial: dict[str, Any],
    ) -> dict[str, Any]:
        business = impact["business_impact"]
        return {
            "Applications Impacted": business["Applications Impacted"],
            "Business Services": business["Business Services"],
            "Departments": business["Departments"],
            "Customers": business["Customers"],
            "Revenue Exposure Per Day": financial["Revenue Exposure Per Day"],
            "Duration Weeks": assumptions["Duration Weeks"],
        }

    @staticmethod
    def _ai_recommendation(
        asset: str,
        scenario: str,
        risk: dict[str, Any],
        business: dict[str, Any],
        financial: dict[str, Any],
        approvals: list[dict[str, Any]],
        assumptions: dict[str, Any],
    ) -> dict[str, Any]:
        if risk["score"] >= 80 and _safe_float(financial["Revenue Exposure Per Day"]) > 0:
            recommendation = "Do NOT execute"
            alternative = "Run a phased mitigation, validate DR, or resize instead of removing capacity."
        elif risk["score"] >= 60:
            recommendation = "Proceed with approval gates"
            alternative = "Pilot in a lower environment, then phase production rollout."
        else:
            recommendation = "Proceed"
            alternative = "Monitor post-change cost, availability, and customer experience."
        ai_summary = (
            f"Simulation shows {scenario} for {asset} changes annual cost by "
            f"{_money(financial['Budget Impact'])} and creates {_money(financial['Revenue Exposure Per Day'])}/day "
            f"of revenue exposure. {business['Applications Impacted']} applications and "
            f"{business['Business Services']} business services are in scope. Risk is {risk['level']}."
        )
        return {
            "AI Summary": ai_summary,
            "Recommendation": recommendation,
            "Alternative": alternative,
            "Confidence": assumptions["Confidence"],
            "Approvals Required": ", ".join(row["Approver Role"] for row in approvals if row.get("Required") == "Yes"),
        }

    @staticmethod
    def _executive_summary(
        asset: str,
        scenario: str,
        business: dict[str, Any],
        financial: dict[str, Any],
        risk: dict[str, Any],
        recommendation: dict[str, Any],
    ) -> str:
        return (
            f"{scenario} for {asset} would affect {business['Applications Impacted']} applications, "
            f"{business['Business Services']} business services, {business['Departments']} departments, "
            f"and {business['Customers']:,} customers. Revenue exposure is "
            f"{_money(financial['Revenue Exposure Per Day'])}/day, expected monthly savings are "
            f"{_money(financial['Expected Monthly Savings'])}, and risk is {risk['level']}. "
            f"Recommendation: {recommendation['Recommendation']}."
        )

    @staticmethod
    def _status_from_recommendation(recommendation: dict[str, Any]) -> str:
        if recommendation["Recommendation"] == "Do NOT execute":
            return "Rejected"
        if "approval" in recommendation["Recommendation"].lower():
            return "Review"
        return "Approved"

    @staticmethod
    def _persist(simulation: dict[str, Any]) -> None:
        run_payload = {
            "id": simulation["id"],
            "organization_id": simulation["organization_id"],
            "simulation_name": simulation["simulation_name"],
            "asset_id": simulation["asset_id"],
            "asset_type": simulation["asset_type"],
            "scenario": simulation["scenario"],
            "status": simulation["status"],
            "created_by": simulation["created_by"],
            "created_at": simulation["created_at"],
            "simulation_results": simulation,
        }
        result_payload = {
            "simulation_id": simulation["id"],
            "organization_id": simulation["organization_id"],
            "impact_score": simulation["impact_analysis"]["impact_score"],
            "financial_score": max(min(abs(_safe_float(simulation["financial_analysis"]["Budget Impact"])) / max(_safe_float(simulation["financial_analysis"]["Current Annual Cost"]), 1) * 100, 100), 0),
            "risk_score": simulation["risk_analysis"]["score"],
            "ai_summary": simulation["ai_recommendation"]["AI Summary"],
            "confidence": simulation["ai_recommendation"]["Confidence"],
            "approvals": simulation["approval_analysis"],
            "created_at": simulation["created_at"],
        }
        SimulationRepository.save_run(run_payload)
        SimulationRepository.save_result(result_payload)
        EnterpriseIntelligenceService.log_intelligence_event(
            event_type="SIMULATION_RUN",
            user_id=simulation.get("created_by") or "system",
            action="run",
            resource_type="simulation",
            resource_id=simulation["id"],
            organization_id=simulation["organization_id"],
            details={
                "asset": simulation["asset_id"],
                "scenario": simulation["scenario"],
                "status": simulation["status"],
                "risk": simulation["risk_analysis"]["level"],
            },
        )

    @staticmethod
    def _summary_row(simulation: dict[str, Any]) -> dict[str, Any]:
        return {
            "Simulation": simulation["simulation_name"],
            "Asset": simulation["asset_id"],
            "Scenario": simulation["scenario"],
            "Status": simulation["status"],
            "Risk": simulation["risk_analysis"]["level"],
            "Risk Score": simulation["risk_analysis"]["score"],
            "Confidence": simulation["ai_recommendation"]["Confidence"],
            "Recommendation": simulation["ai_recommendation"]["Recommendation"],
        }

    @staticmethod
    def _report_sections(simulation: dict[str, Any]) -> list[tuple[str, list[str]]]:
        return [
            ("Executive Summary", [simulation["executive_summary"]]),
            ("AI Recommendation", [simulation["ai_recommendation"]["AI Summary"], simulation["ai_recommendation"]["Alternative"]]),
            ("Business Impact", [f"{key}: {value}" for key, value in simulation["business_impact"].items()]),
            ("Financial Analysis", [f"{key}: {value}" for key, value in simulation["financial_analysis"].items()]),
            ("Risk", [f"{key}: {value}" for key, value in simulation["risk_analysis"]["summary"].items()]),
            ("Approvals", [f"{row['Approver Role']}: {row['Approver']} ({row['Status']})" for row in simulation["approval_analysis"]]),
        ]
