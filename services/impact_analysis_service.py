from __future__ import annotations

import zipfile
from datetime import datetime
from io import BytesIO
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from graph.graph_traversal import TraversalType, traverse_graph
from graph.impact_scoring import calculate_impact_score
from repositories.impact_repository import ImpactRepository
from services.enterprise_graph_service import EnterpriseGraphService

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except ImportError:  # pragma: no cover
    letter = None
    canvas = None


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_currency(value: Any) -> str:
    return f"${_safe_float(value):,.0f}"


class ImpactAnalysisService:
    @staticmethod
    def analyze_asset(
        asset: str,
        asset_type: str | None = None,
        organization_id: str | None = None,
        traversal_type: TraversalType | str = TraversalType.ALL_IMPACTS,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        graph = EnterpriseGraphService.build_graph(org_id)
        graph_data = EnterpriseGraphService._cached_graph(org_id)
        node = EnterpriseGraphService.get_node(asset, org_id)
        resolved_asset = node["name"] if node else asset
        resolved_type = asset_type or (node.get("type") if node else "Unknown")

        if use_cache:
            cached = ImpactRepository.get_cached_analysis(resolved_asset, resolved_type, org_id)
            if cached and cached.get("analysis_payload") and cached["analysis_payload"].get("why_critical"):
                return cached["analysis_payload"]

        traversal = traverse_graph(
            resolved_asset,
            organization_id=org_id,
            traversal_type=traversal_type,
            depth=6,
        )
        rows = traversal["nodes"]
        context = ImpactRepository.load_context(org_id)
        counts = ImpactAnalysisService._counts(rows)
        annual_cost = ImpactAnalysisService._annual_cost(resolved_asset, rows, context)
        savings = ImpactAnalysisService._savings(rows, context)
        revenue_risk = ImpactAnalysisService._revenue_risk(counts, annual_cost)
        approvals = ImpactAnalysisService._approvals(rows, context)
        risks = ImpactAnalysisService._risk_inputs(counts, annual_cost, revenue_risk, approvals)
        scoring = calculate_impact_score(risks)

        dependency_tree = ImpactAnalysisService._dependency_tree(resolved_asset, rows)
        business_impact = ImpactAnalysisService._business_impact(counts, revenue_risk, approvals)
        financial_impact = ImpactAnalysisService._financial_impact(annual_cost, savings, revenue_risk)
        risk_analysis = ImpactAnalysisService._risk_analysis(scoring, risks, approvals)
        approval_intelligence = ImpactAnalysisService._approval_intelligence(approvals, rows, scoring)
        why_critical = ImpactAnalysisService._why_critical(
            counts,
            financial_impact,
            risk_analysis,
            scoring,
        )
        impact_hierarchy = ImpactAnalysisService._impact_hierarchy(
            resolved_asset,
            resolved_type,
            rows,
            financial_impact,
            business_impact,
        )
        impact_heat_map = ImpactAnalysisService._impact_heat_map(rows, scoring)
        blast_radius = ImpactAnalysisService._blast_radius(
            resolved_asset,
            business_impact,
            financial_impact,
        )
        explainability = ImpactAnalysisService._explainability(
            rows,
            scoring,
            financial_impact,
            risk_analysis,
            approval_intelligence,
        )
        executive_summary = ImpactAnalysisService._executive_summary(
            resolved_asset,
            resolved_type,
            scoring,
            business_impact,
            financial_impact,
        )

        analysis = {
            "organization_id": org_id,
            "asset": resolved_asset,
            "asset_type": resolved_type,
            "generated_at": datetime.utcnow().isoformat(),
            "impact_score": scoring["impact_score"],
            "risk_score": scoring["risk_score"],
            "risk_level": scoring["risk_level"],
            "executive_summary": executive_summary,
            "summary": {
                "Technology": resolved_asset,
                "Type": resolved_type,
                "Impact Score": scoring["impact_score"],
                "Risk": scoring["risk_level"],
                "Applications": counts["applications"],
                "Business Services": counts["business_services"],
                "Departments": counts["departments"],
                "Owners": counts["owners"],
                "Annual Cost": annual_cost,
                "Revenue Risk": revenue_risk,
                "Approvals Required": len(approvals),
            },
            "business_impact": business_impact,
            "financial_impact": financial_impact,
            "risk_analysis": risk_analysis,
            "approval_intelligence": approval_intelligence,
            "why_critical": why_critical,
            "impact_hierarchy": impact_hierarchy,
            "impact_heat_map": impact_heat_map,
            "blast_radius": blast_radius,
            "explainability": explainability,
            "ai_context": ImpactAnalysisService._ai_context(
                resolved_asset,
                resolved_type,
                rows,
                executive_summary,
                business_impact,
                financial_impact,
                risk_analysis,
                why_critical,
                explainability,
                approval_intelligence,
            ),
            "dependency_tree": dependency_tree,
            "impacted_nodes": rows,
            "impacted_edges": traversal["edges"],
            "graph_summary": graph["metrics"],
            "score_components": scoring["components"],
        }
        ImpactAnalysisService._cache_analysis(analysis)
        return analysis

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        graph = EnterpriseGraphService.build_graph(org_id)
        nodes = graph["nodes"]
        sample_nodes = [
            node for node in nodes if node["type"] in {"Technology", "Cloud Provider", "Application", "Business Service"}
        ][:30]
        analysed = [ImpactAnalysisService.analyze_asset(node["name"], node["type"], org_id, use_cache=False) for node in sample_nodes]
        critical = [row for row in analysed if row["risk_level"] in {"Critical", "High"}]
        total_revenue = sum(row["financial_impact"]["Estimated Revenue Risk"] for row in analysed)
        total_cost = sum(row["financial_impact"]["Annual Cost"] for row in analysed)
        avg_score = round(sum(row["impact_score"] for row in analysed) / len(analysed), 1) if analysed else 0.0
        return {
            "kpis": {
                "Assets Analysed": len(analysed),
                "Critical Assets": len(critical),
                "Business Services": len({node["name"] for node in nodes if node["type"] == "Business Service"}),
                "Revenue Exposure": total_revenue,
                "Applications": len({node["name"] for node in nodes if node["type"] == "Application"}),
                "Departments": len({node["name"] for node in nodes if node["type"] in {"Department", "Business Unit"}}),
                "Estimated Risk": sum(row["risk_score"] for row in analysed),
                "Average Impact Score": avg_score,
                "Annual Cost Exposure": total_cost,
            },
            "assets": sorted(
                [{"name": node["name"], "type": node["type"]} for node in nodes],
                key=lambda row: (row["type"], row["name"]),
            ),
            "top_impacts": sorted(
                [row["summary"] for row in analysed],
                key=lambda row: row["Impact Score"],
                reverse=True,
            ),
        }

    @staticmethod
    def build_pdf(analysis: dict[str, Any]) -> bytes:
        if canvas is None or letter is None:
            raise RuntimeError("PDF export requires reportlab.")
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle(f"Impact Analysis - {analysis['asset']}")
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, 760, f"Nexora - Impact Analysis: {analysis['asset']}")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, 742, f"Generated: {analysis['generated_at'][:19]} UTC")
        y = 710
        for title, lines in ImpactAnalysisService._report_sections(analysis):
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
    def build_excel(analysis: dict[str, Any]) -> bytes:
        sheets = {
            "Summary": [analysis["summary"]],
            "Why Critical": analysis.get("why_critical", []),
            "Business Impact": [analysis["business_impact"]],
            "Financial Impact": [analysis["financial_impact"]],
            "Risk": [analysis["risk_analysis"]],
            "Approvals": analysis.get("approval_intelligence", []),
            "Explainability": analysis.get("explainability", []),
            "Hierarchy": analysis.get("impact_hierarchy", []),
            "Heat Map": analysis.get("impact_heat_map", []),
            "Impacted Nodes": analysis["impacted_nodes"],
        }
        return _minimal_xlsx(sheets)

    @staticmethod
    def build_powerpoint(analysis: dict[str, Any]) -> bytes:
        slides = [
            (
                f"Impact Analysis: {analysis['asset']}",
                [
                    analysis["executive_summary"],
                    f"Impact score: {analysis['impact_score']} ({analysis['risk_level']})",
                ],
            ),
            (
                "Business Impact",
                [f"{key}: {value}" for key, value in analysis["business_impact"].items()],
            ),
            (
                "Financial Impact",
                [f"{key}: {_fmt_currency(value) if isinstance(value, (int, float)) else value}" for key, value in analysis["financial_impact"].items()],
            ),
            (
                "Risk And Approvals",
                [f"{key}: {value}" for key, value in analysis["risk_analysis"].items()]
                + [
                    f"{row.get('Approver Role')}: {row.get('Approver')} ({row.get('Status')})"
                    for row in analysis.get("approval_intelligence", [])[:5]
                ],
            ),
            (
                "Why Critical",
                [row["Reason"] for row in analysis.get("why_critical", [])],
            ),
        ]
        return _minimal_pptx(slides)

    @staticmethod
    def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        def count(*types: str) -> int:
            return len({row["node"] for row in rows if row["node_type"] in types})

        return {
            "applications": count("Application"),
            "business_services": count("Business Service"),
            "business_capabilities": count("Business Capability"),
            "departments": count("Department", "Business Unit", "Cost Center"),
            "owners": count("Owner", "Team"),
            "cloud_resources": count("Cloud Resource", "Enterprise Asset", "Cloud Provider"),
            "recommendations": count("Recommendation"),
            "workflows": count("Workflow", "Execution"),
            "audits": count("Audit"),
            "total_dependencies": len(rows),
        }

    @staticmethod
    def _annual_cost(asset: str, rows: list[dict[str, Any]], context: dict[str, Any]) -> float:
        names = {asset.lower(), *[row["node"].lower() for row in rows]}
        total = 0.0
        for table in ("application_spend_mapping", "vw_vendor_spend", "vw_department_spend", "technology_inventory"):
            for row in context.get(table, []):
                row_text = " ".join(str(value).lower() for value in row.values() if value is not None)
                if not any(name and name in row_text for name in names):
                    continue
                total += _first_number(row, "annual_cost", "annual_spend", "total_spend", "spend", "amount", "cost")
        for row in rows:
            metadata = row.get("metadata") or {}
            total += _first_number(metadata, "amount", "annual_cost", "cost")
        return round(total, 2)

    @staticmethod
    def _savings(rows: list[dict[str, Any]], context: dict[str, Any]) -> float:
        names = {row["node"].lower() for row in rows}
        total = 0.0
        for table in ("cost_recommendations", "ai_recommendation_history"):
            for row in context.get(table, []):
                row_text = " ".join(str(value).lower() for value in row.values() if value is not None)
                if names and not any(name in row_text for name in names):
                    continue
                total += _first_number(row, "estimated_savings", "savings", "projected_savings", "annual_savings")
        return round(total, 2)

    @staticmethod
    def _revenue_risk(counts: dict[str, int], annual_cost: float) -> float:
        service_exposure = counts["business_services"] * 750_000
        app_exposure = counts["applications"] * 250_000
        cost_exposure = annual_cost * 1.5
        return round(service_exposure + app_exposure + cost_exposure, 2)

    @staticmethod
    def _approvals(rows: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
        owners = {row["node"] for row in rows if row["node_type"] in {"Owner", "Team"}}
        approvals = []
        for table in ("approval_queue", "approval_requests", "workflow_history", "ai_workflow_actions"):
            for row in context.get(table, []):
                status = str(row.get("status") or row.get("execution_status") or "").lower()
                if status in {"approved", "completed", "rejected"}:
                    continue
                approvals.append(
                    {
                        "source": table,
                        "owner": row.get("owner") or row.get("requested_by") or row.get("approver") or ", ".join(sorted(owners)) or "Unassigned",
                        "status": row.get("status") or row.get("execution_status") or "Required",
                        "action": row.get("action_type") or row.get("request_type") or row.get("title") or "Change approval",
                    }
                )
        if not approvals and owners:
            approvals = [{"source": "derived", "owner": owner, "status": "Required", "action": "Owner approval"} for owner in sorted(owners)[:5]]
        return approvals[:20]

    @staticmethod
    def _risk_inputs(
        counts: dict[str, int],
        annual_cost: float,
        revenue_risk: float,
        approvals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "business_criticality": min(counts["business_services"] * 15 + counts["business_capabilities"] * 20, 100),
            "dependency_count": counts["total_dependencies"],
            "revenue_impact": revenue_risk,
            "cost_exposure": annual_cost,
            "operational_risk": min(counts["cloud_resources"] * 8 + counts["workflows"] * 10, 100),
            "security_risk": min(counts["cloud_resources"] * 7 + counts["owners"] * 3, 100),
            "compliance": min(counts["audits"] * 20 + len(approvals) * 6, 100),
            "executive_visibility": min(counts["owners"] * 8 + counts["departments"] * 12, 100),
        }

    @staticmethod
    def _business_impact(counts: dict[str, int], revenue_risk: float, approvals: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "Applications Impacted": counts["applications"],
            "Business Services": counts["business_services"],
            "Customers": max(counts["business_services"] * 25000, counts["applications"] * 7500),
            "Revenue": revenue_risk,
            "Revenue Per Day": round(revenue_risk / 365, 2),
            "Departments": counts["departments"],
            "Owners": counts["owners"],
            "Approvals Required": len(approvals),
        }

    @staticmethod
    def _financial_impact(annual_cost: float, savings: float, revenue_risk: float) -> dict[str, Any]:
        return {
            "Cloud Spend": annual_cost,
            "Savings": savings,
            "License Cost": round(annual_cost * 0.35, 2),
            "Support Cost": round(annual_cost * 0.12, 2),
            "Estimated Revenue Risk": revenue_risk,
            "Estimated Revenue Risk Per Day": round(revenue_risk / 365, 2),
            "Annual Cost": annual_cost,
        }

    @staticmethod
    def _risk_analysis(
        scoring: dict[str, Any],
        risks: dict[str, Any],
        approvals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "Technical Risk": round((risks["operational_risk"] + risks["security_risk"]) / 2, 1),
            "Business Risk": round(risks["business_criticality"], 1),
            "Financial Risk": round((scoring["components"]["cost_exposure"] + scoring["components"]["revenue_impact"]) / 2, 1),
            "Compliance Risk": round(risks["compliance"], 1),
            "Operational Risk": round(risks["operational_risk"], 1),
            "Overall Risk": scoring["risk_level"],
            "Risk Score": scoring["risk_score"],
            "Approvals": len(approvals),
            "Automation Readiness": "Low" if scoring["risk_score"] >= 75 or approvals else "Medium" if scoring["risk_score"] >= 50 else "High",
        }

    @staticmethod
    def _executive_summary(
        asset: str,
        asset_type: str,
        scoring: dict[str, Any],
        business: dict[str, Any],
        financial: dict[str, Any],
    ) -> str:
        return (
            f"{asset} ({asset_type}) has an impact score of {scoring['impact_score']:.1f} "
            f"and is classified as {scoring['risk_level']}. It is connected to "
            f"{business['Applications Impacted']} applications, {business['Business Services']} business services, "
            f"{business['Departments']} departments, and {business['Owners']} owners. Annual cost exposure is "
            f"{_fmt_currency(financial['Annual Cost'])}, with estimated revenue risk of "
            f"{_fmt_currency(financial['Estimated Revenue Risk'])} and optimization potential of "
            f"{_fmt_currency(financial['Savings'])}."
        )

    @staticmethod
    def _ai_context(
        asset: str,
        asset_type: str,
        rows: list[dict[str, Any]],
        summary: str,
        business: dict[str, Any],
        financial: dict[str, Any],
        risk: dict[str, Any],
        why_critical: list[dict[str, Any]],
        explainability: list[dict[str, Any]],
        approval_intelligence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "prompt_context": summary,
            "asset": asset,
            "asset_type": asset_type,
            "business_impact": business,
            "financial_impact": financial,
            "risk_analysis": risk,
            "why_critical": why_critical,
            "explainability": explainability,
            "approval_intelligence": approval_intelligence,
            "top_impacts": [
                {"node": row["node"], "type": row["node_type"], "depth": row["depth"]}
                for row in rows[:25]
            ],
            "recommended_answer_style": "Answer in executive terms first, then give dependency, owner, approval, risk, and automation detail.",
        }

    @staticmethod
    def _impact_hierarchy(
        asset: str,
        asset_type: str,
        rows: list[dict[str, Any]],
        financial: dict[str, Any],
        business: dict[str, Any],
    ) -> list[dict[str, Any]]:
        levels = [
            ("Technology", {"Technology", "Cloud Provider", "Vendor", "Selected Asset"}),
            ("Infrastructure", {"Enterprise Asset", "Cloud Resource", "Environment"}),
            ("Application", {"Application"}),
            ("Business Service", {"Business Service"}),
            ("Business Capability", {"Business Capability"}),
            ("Department", {"Department", "Business Unit", "Cost Center"}),
            ("Executive", {"Owner", "Team"}),
        ]
        hierarchy = [
            {
                "Level": "Technology",
                "Entity": asset,
                "Type": asset_type,
                "Parent": "",
                "Depth": 0,
                "Relationship": "ROOT",
                "Impact Weight": 100,
            }
        ]
        seen = {("Technology", asset)}
        parent_by_level = {"Technology": asset}
        for level_name, node_types in levels:
            for row in rows:
                if row["node_type"] not in node_types:
                    continue
                key = (level_name, row["node"])
                if key in seen:
                    continue
                seen.add(key)
                parent = ImpactAnalysisService._nearest_hierarchy_parent(level_name, parent_by_level)
                hierarchy.append(
                    {
                        "Level": level_name,
                        "Entity": row["node"],
                        "Type": row["node_type"],
                        "Parent": parent,
                        "Depth": row["depth"],
                        "Relationship": row["relationship"],
                        "Impact Weight": max(15, 100 - (int(row["depth"]) * 10)),
                    }
                )
                parent_by_level[level_name] = row["node"]

        derived = [
            ("Revenue", "Revenue Exposure", _fmt_currency(financial["Estimated Revenue Risk"])),
            ("Compliance", "Compliance Exposure", "Regulated change review required"),
            ("Customers", "Customer Exposure", f"{business['Customers']:,} customers"),
        ]
        parent = parent_by_level.get("Department") or parent_by_level.get("Business Capability") or asset
        for level_name, entity, value in derived:
            hierarchy.append(
                {
                    "Level": level_name,
                    "Entity": entity,
                    "Type": value,
                    "Parent": parent,
                    "Depth": 8,
                    "Relationship": "DERIVED_IMPACT",
                    "Impact Weight": 60,
                }
            )
        return hierarchy

    @staticmethod
    def _nearest_hierarchy_parent(level_name: str, parent_by_level: dict[str, str]) -> str:
        order = [
            "Technology",
            "Infrastructure",
            "Application",
            "Business Service",
            "Business Capability",
            "Department",
            "Executive",
        ]
        try:
            index = order.index(level_name)
        except ValueError:
            return parent_by_level.get("Technology", "")
        for candidate in reversed(order[:index]):
            if parent_by_level.get(candidate):
                return parent_by_level[candidate]
        return parent_by_level.get("Technology", "")

    @staticmethod
    def _impact_heat_map(rows: list[dict[str, Any]], scoring: dict[str, Any]) -> list[dict[str, Any]]:
        base = float(scoring["impact_score"])
        heat_rows = []
        for row in rows:
            if row["node_type"] not in {
                "Application",
                "Business Service",
                "Business Capability",
                "Department",
                "Business Unit",
                "Owner",
                "Cloud Resource",
                "Enterprise Asset",
            }:
                continue
            score = max(1.0, min(100.0, base - (float(row["depth"]) * 5)))
            heat_rows.append(
                {
                    "Category": row["node_type"],
                    "Entity": row["node"],
                    "Impact Score": round(score, 1),
                    "Risk": _risk_label(score),
                    "Depth": row["depth"],
                }
            )
        return sorted(heat_rows, key=lambda item: item["Impact Score"], reverse=True)[:40]

    @staticmethod
    def _blast_radius(
        asset: str,
        business: dict[str, Any],
        financial: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {"Ring": 0, "Node": asset, "Parent": "", "Value": 1, "Display": "Selected asset"},
            {"Ring": 1, "Node": "Applications", "Parent": asset, "Value": max(business["Applications Impacted"], 1), "Display": f"{business['Applications Impacted']} applications"},
            {"Ring": 2, "Node": "Business Services", "Parent": "Applications", "Value": max(business["Business Services"], 1), "Display": f"{business['Business Services']} business services"},
            {"Ring": 3, "Node": "Departments", "Parent": "Business Services", "Value": max(business["Departments"], 1), "Display": f"{business['Departments']} departments"},
            {"Ring": 4, "Node": "Owners", "Parent": "Departments", "Value": max(business["Owners"], 1), "Display": f"{business['Owners']} owners"},
            {"Ring": 5, "Node": "Revenue Exposure", "Parent": "Owners", "Value": max(financial["Estimated Revenue Risk"], 1), "Display": _fmt_currency(financial["Estimated Revenue Risk"])},
        ]

    @staticmethod
    def _approval_intelligence(
        approvals: list[dict[str, Any]],
        rows: list[dict[str, Any]],
        scoring: dict[str, Any],
    ) -> list[dict[str, Any]]:
        owners = sorted({row["node"] for row in rows if row["node_type"] in {"Owner", "Team"}})
        departments = sorted({row["node"] for row in rows if row["node_type"] in {"Department", "Business Unit"}})
        roles = [
            ("Business Owner", owners[0] if owners else "Business owner", "Business service or capability impact"),
            ("Technology Owner", owners[1] if len(owners) > 1 else owners[0] if owners else "Technology owner", "Technology or infrastructure dependency"),
            ("Finance", departments[0] if departments else "Finance", "Cost and revenue exposure"),
            ("Security", "Security", "Security and operational risk review"),
            ("CAB", "Change Advisory Board", "Enterprise blast radius and change control"),
        ]
        status_by_owner = {
            str(row.get("owner") or "").lower(): str(row.get("status") or "Required")
            for row in approvals
        }
        intelligence = []
        for role, approver, reason in roles:
            required = role in {"Business Owner", "Technology Owner", "Finance"} or scoring["risk_score"] >= 70
            intelligence.append(
                {
                    "Approver Role": role,
                    "Approver": approver,
                    "Required": "Yes" if required else "Conditional",
                    "Reason": reason,
                    "Status": status_by_owner.get(str(approver).lower(), "Required" if required else "Conditional"),
                }
            )
        return intelligence

    @staticmethod
    def _why_critical(
        counts: dict[str, int],
        financial: dict[str, Any],
        risk: dict[str, Any],
        scoring: dict[str, Any],
    ) -> list[dict[str, Any]]:
        reasons = [
            (counts["applications"], f"Supports {counts['applications']} applications", "Dependency Count"),
            (counts["business_services"], f"Supports {counts['business_services']} business services", "Business Criticality"),
            (counts["departments"], f"Used by {counts['departments']} departments or cost centers", "Executive Visibility"),
            (financial["Annual Cost"], f"Annual spend is {_fmt_currency(financial['Annual Cost'])}", "Cost Exposure"),
            (financial["Estimated Revenue Risk Per Day"], f"Revenue exposure is {_fmt_currency(financial['Estimated Revenue Risk Per Day'])}/day", "Revenue Impact"),
            (risk["Compliance Risk"], f"Compliance risk score is {risk['Compliance Risk']:.1f}", "Compliance"),
            (risk["Operational Risk"], f"Operational risk score is {risk['Operational Risk']:.1f}", "Operational Risk"),
        ]
        return [
            {
                "Reason": reason,
                "Driver": driver,
                "Evidence": round(float(value or 0), 2),
                "Contribution": round(scoring["components"].get(_driver_key(driver), 0), 1),
            }
            for value, reason, driver in reasons
            if float(value or 0) > 0
        ]

    @staticmethod
    def _explainability(
        rows: list[dict[str, Any]],
        scoring: dict[str, Any],
        financial: dict[str, Any],
        risk: dict[str, Any],
        approvals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        relationships = sorted({str(row.get("relationship") or "RELATED_TO") for row in rows if row.get("relationship")})
        return [
            {
                "Why": "Enterprise blast radius is high",
                "Which Relationships": ", ".join(relationships[:6]) or "Graph traversal",
                "Business Rule": "Impact score weights business criticality, dependencies, revenue, cost, operational, security, compliance, and executive visibility.",
                "Confidence": "95%",
                "Expected Savings": _fmt_currency(financial["Savings"]),
                "Risk": risk["Overall Risk"],
                "Approvals": len(approvals),
            },
            {
                "Why": "Automation should be gated",
                "Which Relationships": "Owner, department, workflow, and approval dependencies",
                "Business Rule": "Critical or approval-heavy changes require owner, finance, security, and CAB review.",
                "Confidence": "92%",
                "Expected Savings": _fmt_currency(financial["Savings"]),
                "Risk": risk["Automation Readiness"],
                "Approvals": len(approvals),
            },
            {
                "Why": "Financial exposure needs executive visibility",
                "Which Relationships": "Cost, business service, department, and revenue-derived impact",
                "Business Rule": "Revenue or annual cost exposure above materiality thresholds increases executive visibility.",
                "Confidence": "90%",
                "Expected Savings": _fmt_currency(financial["Savings"]),
                "Risk": _risk_label(scoring["impact_score"]),
                "Approvals": len(approvals),
            },
        ]

    @staticmethod
    def _dependency_tree(asset: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tree = [{"Depth": 0, "Entity": asset, "Type": "Selected Asset", "Relationship": "ROOT"}]
        for row in rows[:80]:
            tree.append(
                {
                    "Depth": row["depth"],
                    "Entity": row["node"],
                    "Type": row["node_type"],
                    "Relationship": row["relationship"],
                }
            )
        return tree

    @staticmethod
    def _cache_analysis(analysis: dict[str, Any]) -> None:
        payload = {
            "organization_id": analysis["organization_id"],
            "asset_id": analysis["asset"],
            "asset_type": analysis["asset_type"],
            "impact_score": analysis["impact_score"],
            "risk_score": analysis["risk_score"],
            "business_services": analysis["business_impact"]["Business Services"],
            "applications": analysis["business_impact"]["Applications Impacted"],
            "departments": analysis["business_impact"]["Departments"],
            "owners": analysis["business_impact"]["Owners"],
            "annual_cost": analysis["financial_impact"]["Annual Cost"],
            "revenue_risk": analysis["financial_impact"]["Estimated Revenue Risk"],
            "analysis_payload": analysis,
            "generated_at": datetime.utcnow().isoformat(),
        }
        ImpactRepository.save_cached_analysis(payload)

    @staticmethod
    def _report_sections(analysis: dict[str, Any]) -> list[tuple[str, list[str]]]:
        return [
            ("Executive Summary", [analysis["executive_summary"]]),
            ("Impact Summary", [f"{key}: {value}" for key, value in analysis["summary"].items()]),
            ("Business Impact", [f"{key}: {value}" for key, value in analysis["business_impact"].items()]),
            ("Financial Impact", [f"{key}: {_fmt_currency(value) if isinstance(value, (int, float)) else value}" for key, value in analysis["financial_impact"].items()]),
            ("Why Critical", [row["Reason"] for row in analysis.get("why_critical", [])]),
            ("Risk", [f"{key}: {value}" for key, value in analysis["risk_analysis"].items()]),
            ("Approvals", [f"{row['Approver Role']}: {row['Approver']} ({row['Status']})" for row in analysis.get("approval_intelligence", [])]),
            ("Dependencies", [f"{row['Depth']} - {row['Entity']} ({row['Type']})" for row in analysis["dependency_tree"][:30]]),
            ("Recommendations", [analysis["ai_context"]["recommended_answer_style"]]),
        ]


def _first_number(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        if key in row:
            return _safe_float(row.get(key))
    return 0.0


def _risk_label(score: Any) -> str:
    score_value = _safe_float(score)
    if score_value >= 85:
        return "Critical"
    if score_value >= 70:
        return "High"
    if score_value >= 45:
        return "Medium"
    return "Low"


def _driver_key(driver: str) -> str:
    return {
        "Business Criticality": "business_criticality",
        "Dependency Count": "dependency_count",
        "Revenue Impact": "revenue_impact",
        "Cost Exposure": "cost_exposure",
        "Operational Risk": "operational_risk",
        "Security Risk": "security_risk",
        "Compliance": "compliance",
        "Executive Visibility": "executive_visibility",
    }.get(driver, "")


def _minimal_xlsx(sheets: dict[str, list[dict[str, Any]]]) -> bytes:
    shared_strings: list[str] = []
    shared_index: dict[str, int] = {}

    def string_id(value: Any) -> int:
        text = str(value if value is not None else "")
        if text not in shared_index:
            shared_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_index[text]

    sheet_xml = []
    for sheet_name, rows in sheets.items():
        columns = sorted({key for row in rows for key in row.keys()}) if rows else ["Message"]
        matrix = [columns]
        matrix.extend([[row.get(column, "") for column in columns] for row in rows])
        xml_rows = []
        for row_index, values in enumerate(matrix, start=1):
            cells = []
            for col_index, value in enumerate(values, start=1):
                ref = f"{_excel_col(col_index)}{row_index}"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                else:
                    cells.append(f'<c r="{ref}" t="s"><v>{string_id(value)}</v></c>')
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        sheet_xml.append((sheet_name[:31], f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'))

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _xlsx_content_types(len(sheet_xml)))
        zf.writestr("_rels/.rels", _rels("xl/workbook.xml"))
        zf.writestr("xl/workbook.xml", _workbook_xml([name for name, _ in sheet_xml]))
        zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(len(sheet_xml)))
        zf.writestr("xl/sharedStrings.xml", _shared_strings_xml(shared_strings))
        for index, (_name, xml) in enumerate(sheet_xml, start=1):
            zf.writestr(f"xl/worksheets/sheet{index}.xml", xml)
    return buffer.getvalue()


def _excel_col(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xlsx_content_types(sheet_count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        f"{sheets}</Types>"
    )


def _rels(target: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{target}"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{_xml_escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'
    )


def _workbook_rels(sheet_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    rels += f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
    return f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'


def _shared_strings_xml(strings: list[str]) -> str:
    items = "".join(f"<si><t>{_xml_escape(text)}</t></si>" for text in strings)
    return f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">{items}</sst>'


def _minimal_pptx(slides: list[tuple[str, list[str]]]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _ppt_content_types(len(slides)))
        zf.writestr("_rels/.rels", _rels("ppt/presentation.xml"))
        zf.writestr("ppt/presentation.xml", _ppt_presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", _ppt_rels(len(slides)))
        for index, (title, bullets) in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{index}.xml", _ppt_slide_xml(title, bullets))
    return buffer.getvalue()


def _ppt_content_types(slide_count: int) -> str:
    slides = "".join(
        f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        f"{slides}</Types>"
    )


def _ppt_presentation_xml(slide_count: int) -> str:
    slide_ids = "".join(f'<p:sldId id="{256 + index}" r:id="rId{index}"/>' for index in range(1, slide_count + 1))
    return (
        '<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst>{slide_ids}</p:sldIdLst></p:presentation>'
    )


def _ppt_rels(slide_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, slide_count + 1)
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'


def _ppt_slide_xml(title: str, bullets: list[str]) -> str:
    body = "\n".join(f"<a:p><a:r><a:t>{_xml_escape(bullet)}</a:t></a:r></a:p>" for bullet in bullets[:10])
    return (
        '<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:txBody><a:bodyPr/><a:lstStyle/>'
        f"<a:p><a:r><a:t>{_xml_escape(title)}</a:t></a:r></a:p></p:txBody></p:sp>"
        '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:txBody><a:bodyPr/><a:lstStyle/>'
        f"{body}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )


def _xml_escape(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
