from __future__ import annotations

import uuid
from datetime import datetime
from io import BytesIO
from typing import Any

from ai.confidence_engine import score_confidence
from ai.context_builder import build_reasoning_context
from ai.policy_engine import DEFAULT_POLICIES, evaluate_policies
from connectors.common.tenant_guard import resolve_organization_id
from repositories.ai_reasoning_repository import AIReasoningRepository
from services.enterprise_intelligence_service import EnterpriseIntelligenceService
from services.impact_analysis_service import _minimal_pptx, _minimal_xlsx

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


def _money(value: Any) -> str:
    return f"${_safe_float(value):,.0f}"


class AIReasoningService:
    @staticmethod
    def reason(
        question: str,
        organization_id: str | None = None,
        scenario_type: str | None = None,
        scenario: str | None = None,
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        context = build_reasoning_context(question, org_id, scenario_type, scenario)
        configured = AIReasoningRepository.get_policy_rules(org_id)
        policies = evaluate_policies(context, configured or DEFAULT_POLICIES)
        evidence = AIReasoningService._evidence(context)
        alternatives = AIReasoningService._alternatives(context)
        confidence = score_confidence(context, policies)
        recommendation = AIReasoningService._recommendation(context, policies, alternatives)
        reasoning_chain = AIReasoningService._reasoning_chain(
            question,
            context,
            evidence,
            policies,
            alternatives,
            recommendation,
            confidence,
        )
        explanation = AIReasoningService._explanation(
            context,
            evidence,
            policies,
            alternatives,
            recommendation,
            confidence,
        )
        result = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "question": question,
            "asset": context.get("asset") or "Unknown",
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "recommendation": recommendation,
            "reasoning": reasoning_chain,
            "evidence": evidence,
            "policies": policies,
            "alternatives": alternatives,
            "confidence": confidence,
            "explanation": explanation,
            "context_summary": AIReasoningService._context_summary(context),
            "expected_outcome": AIReasoningService._expected_outcome(context, recommendation),
        }
        if persist:
            AIReasoningService._persist(result)
        return result

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        history = AIReasoningRepository.get_history(org_id)
        accepted = [
            row for row in history
            if str(row.get("recommendation") or "").lower().startswith(("proceed", "approve"))
        ]
        confidence_values = [_safe_float(row.get("confidence")) for row in history if row.get("confidence") is not None]
        policy_violations = 0
        savings = 0.0
        for row in history:
            policies = row.get("policies") or []
            if isinstance(policies, list):
                policy_violations += len([item for item in policies if item.get("Matched") == "Yes" and item.get("Severity") in {"Critical", "High"}])
            evidence = row.get("evidence") or []
            if isinstance(evidence, list):
                for item in evidence:
                    if str(item.get("Evidence") or "").lower().startswith("expected savings"):
                        savings += _safe_float(str(item.get("Value") or "0").replace("$", "").replace(",", ""))
        return {
            "kpis": {
                "AI Decisions Today": len(history),
                "Recommendations Accepted": len(accepted),
                "Average Confidence": round(sum(confidence_values) / len(confidence_values), 1) if confidence_values else 0.0,
                "Policy Violations": policy_violations,
                "Simulations Reviewed": len([row for row in history if row.get("reasoning")]),
                "Estimated Savings": savings,
            },
            "history": history,
            "policy_rules": AIReasoningRepository.get_policy_rules(org_id) or DEFAULT_POLICIES,
        }

    @staticmethod
    def build_pdf(reasoning: dict[str, Any]) -> bytes:
        if canvas is None or letter is None:
            raise RuntimeError("PDF export requires reportlab.")
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle("AI Reasoning Decision Package")
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, 760, "Nexora - AI Reasoning Decision Package")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, 742, f"Question: {reasoning['question'][:95]}")
        y = 710
        for title, lines in AIReasoningService._report_sections(reasoning):
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
    def build_excel(reasoning: dict[str, Any]) -> bytes:
        return _minimal_xlsx(
            {
                "Summary": [AIReasoningService._summary_row(reasoning)],
                "Reasoning Chain": reasoning["reasoning"],
                "Evidence": reasoning["evidence"],
                "Policies": reasoning["policies"],
                "Alternatives": reasoning["alternatives"],
                "Confidence": [AIReasoningService._confidence_row(reasoning["confidence"])],
            }
        )

    @staticmethod
    def build_powerpoint(reasoning: dict[str, Any]) -> bytes:
        slides = [
            (
                "AI Reasoning Decision",
                [
                    f"Question: {reasoning['question']}",
                    f"Recommendation: {reasoning['recommendation']['Decision']}",
                    f"Confidence: {reasoning['confidence']['Confidence']}%",
                ],
            ),
            ("Why", [reasoning["explanation"]["Why"]]),
            ("Evidence", [f"{row['Evidence']}: {row['Value']}" for row in reasoning["evidence"][:8]]),
            ("Policies Applied", [f"{row['Rule']}: {row['Action']}" for row in reasoning["policies"] if row["Matched"] == "Yes"] or ["No blocking policies matched."]),
            ("Alternatives", [f"{row['Alternative']} - {row['Recommendation']}" for row in reasoning["alternatives"]]),
        ]
        return _minimal_pptx(slides)

    @staticmethod
    def _evidence(context: dict[str, Any]) -> list[dict[str, Any]]:
        impact = context.get("impact") or {}
        simulation = context.get("simulation") or {}
        financial = simulation.get("financial_analysis") or impact.get("financial_impact") or {}
        business = simulation.get("business_impact") or impact.get("business_impact") or {}
        risk = simulation.get("risk_analysis") or {}
        evidence = [
            ("Applications impacted", business.get("Applications Impacted")),
            ("Business services impacted", business.get("Business Services")),
            ("Departments impacted", business.get("Departments")),
            ("Customers impacted", business.get("Customers")),
            ("Annual spend", _money(financial.get("Current Annual Cost") or financial.get("Annual Cost"))),
            ("Revenue exposure per day", _money(financial.get("Revenue Exposure Per Day") or financial.get("Estimated Revenue Risk Per Day"))),
            ("Expected savings", _money(financial.get("Expected Annual Savings") or financial.get("Savings"))),
            ("Migration cost", _money(financial.get("Migration Cost"))),
            ("Impact score", impact.get("impact_score")),
            ("Risk score", risk.get("score") or impact.get("risk_score")),
        ]
        return [
            {"Evidence": name, "Value": value, "Source": "Impact/Simulation/Enterprise Graph"}
            for name, value in evidence
            if value not in (None, "", 0, "$0")
        ]

    @staticmethod
    def _alternatives(context: dict[str, Any]) -> list[dict[str, Any]]:
        question = str(context.get("question") or "").lower()
        simulation = context.get("simulation") or {}
        financial = simulation.get("financial_analysis") or {}
        base_savings = _safe_float(financial.get("Expected Annual Savings") or 0)
        if "oracle" in question or "postgres" in question or "migrate" in question:
            return [
                {"Alternative": "Phase 1 - Development", "Risk": "Low", "Savings": _money(base_savings * 0.15), "Time": "4 weeks", "Complexity": "Low", "Recommendation": "Start here."},
                {"Alternative": "Phase 2 - QA", "Risk": "Medium", "Savings": _money(base_savings * 0.35), "Time": "8 weeks", "Complexity": "Medium", "Recommendation": "Proceed after validation."},
                {"Alternative": "Phase 3 - Production", "Risk": "High", "Savings": _money(base_savings), "Time": "18 weeks", "Complexity": "High", "Recommendation": "Require CAB and rollback plan."},
            ]
        if "stop" in question or "decommission" in question:
            return [
                {"Alternative": "Resize Instead", "Risk": "Low", "Savings": _money(base_savings * 0.65), "Time": "1 week", "Complexity": "Low", "Recommendation": "Preferred safer action."},
                {"Alternative": "Disable Non-Production First", "Risk": "Medium", "Savings": _money(base_savings * 0.35), "Time": "2 weeks", "Complexity": "Medium", "Recommendation": "Validate usage before production."},
                {"Alternative": "Full Decommission", "Risk": "High", "Savings": _money(base_savings), "Time": "6 weeks", "Complexity": "High", "Recommendation": "Only after approvals."},
            ]
        return [
            {"Alternative": "Phased rollout", "Risk": "Medium", "Savings": _money(base_savings * 0.75), "Time": "6 weeks", "Complexity": "Medium", "Recommendation": "Balances speed and safety."},
            {"Alternative": "Pilot first", "Risk": "Low", "Savings": _money(base_savings * 0.30), "Time": "2 weeks", "Complexity": "Low", "Recommendation": "Best validation path."},
            {"Alternative": "Do nothing", "Risk": "Low", "Savings": "$0", "Time": "0 weeks", "Complexity": "Low", "Recommendation": "Avoids change risk but leaves savings unrealized."},
        ]

    @staticmethod
    def _recommendation(
        context: dict[str, Any],
        policies: list[dict[str, Any]],
        alternatives: list[dict[str, Any]],
    ) -> dict[str, Any]:
        matched_high = [
            row for row in policies
            if row["Matched"] == "Yes" and row["Severity"] in {"Critical", "High"}
        ]
        simulation = context.get("simulation") or {}
        risk = (simulation.get("risk_analysis") or {}).get("level")
        if matched_high:
            decision = "Proceed in phases with approval gates"
        elif risk in {"Critical", "High"}:
            decision = "Proceed only after mitigation"
        else:
            decision = "Proceed"
        return {
            "Decision": decision,
            "Primary Action": alternatives[0]["Alternative"] if alternatives else "Review manually",
            "Why": "Recommendation balances policy constraints, risk, financial return, approval state, and enterprise impact.",
            "Approvals Required": AIReasoningService._approvals(context),
        }

    @staticmethod
    def _reasoning_chain(
        question: str,
        context: dict[str, Any],
        evidence: list[dict[str, Any]],
        policies: list[dict[str, Any]],
        alternatives: list[dict[str, Any]],
        recommendation: dict[str, Any],
        confidence: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {"Step": 1, "Stage": "Question", "Output": question},
            {"Step": 2, "Stage": "Enterprise Context", "Output": f"Asset: {context.get('asset') or 'Unknown'}"},
            {"Step": 3, "Stage": "Evidence", "Output": f"{len(evidence)} evidence items collected"},
            {"Step": 4, "Stage": "Policies", "Output": f"{len([row for row in policies if row['Matched'] == 'Yes'])} policies matched"},
            {"Step": 5, "Stage": "Risk", "Output": AIReasoningService._risk_text(context)},
            {"Step": 6, "Stage": "Simulation", "Output": AIReasoningService._simulation_text(context)},
            {"Step": 7, "Stage": "Alternatives", "Output": f"{len(alternatives)} alternatives generated"},
            {"Step": 8, "Stage": "Recommendation", "Output": recommendation["Decision"]},
            {"Step": 9, "Stage": "Confidence", "Output": f"{confidence['Confidence']}%"},
            {"Step": 10, "Stage": "Explanation", "Output": recommendation["Why"]},
        ]

    @staticmethod
    def _explanation(
        context: dict[str, Any],
        evidence: list[dict[str, Any]],
        policies: list[dict[str, Any]],
        alternatives: list[dict[str, Any]],
        recommendation: dict[str, Any],
        confidence: dict[str, Any],
    ) -> dict[str, Any]:
        matched = [row for row in policies if row["Matched"] == "Yes"]
        return {
            "Recommendation": recommendation["Decision"],
            "Why": AIReasoningService._why_text(context, recommendation),
            "Evidence": [f"{row['Evidence']}: {row['Value']}" for row in evidence],
            "Policies Applied": [f"{row['Rule']}: {row['Action']}" for row in matched],
            "Alternatives": [row["Alternative"] for row in alternatives],
            "Confidence": f"{confidence['Confidence']}%",
            "Risks": AIReasoningService._risk_text(context),
            "Expected Outcome": AIReasoningService._expected_outcome(context, recommendation),
            "Generated At": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _why_text(context: dict[str, Any], recommendation: dict[str, Any]) -> str:
        simulation = context.get("simulation") or {}
        financial = simulation.get("financial_analysis") or {}
        business = simulation.get("business_impact") or {}
        return (
            f"{recommendation['Decision']} because the change affects "
            f"{business.get('Applications Impacted', 0)} applications and "
            f"{business.get('Business Services', 0)} business services, with "
            f"{_money(financial.get('Revenue Exposure Per Day'))}/day revenue exposure and "
            f"{_money(financial.get('Expected Annual Savings'))} expected annual savings."
        )

    @staticmethod
    def _risk_text(context: dict[str, Any]) -> str:
        simulation = context.get("simulation") or {}
        risk = simulation.get("risk_analysis") or {}
        if risk:
            return f"{risk.get('level')} ({risk.get('score')})"
        impact = context.get("impact") or {}
        return f"{impact.get('risk_level', 'Unknown')} ({impact.get('risk_score', 0)})"

    @staticmethod
    def _simulation_text(context: dict[str, Any]) -> str:
        simulation = context.get("simulation") or {}
        if not simulation:
            return "No simulation was required."
        financial = simulation.get("financial_analysis") or {}
        return (
            f"ROI {financial.get('ROI %', 0)}%, payback {financial.get('Payback Months', 0)} months, "
            f"savings {_money(financial.get('Expected Annual Savings'))}"
        )

    @staticmethod
    def _approvals(context: dict[str, Any]) -> str:
        simulation = context.get("simulation") or {}
        approvals = simulation.get("approval_analysis") or (context.get("impact") or {}).get("approval_intelligence") or []
        required = [row.get("Approver Role") for row in approvals if row.get("Required") == "Yes"]
        return ", ".join(required) if required else "No mandatory approvals identified"

    @staticmethod
    def _context_summary(context: dict[str, Any]) -> dict[str, Any]:
        impact = context.get("impact") or {}
        simulation = context.get("simulation") or {}
        return {
            "Asset": context.get("asset"),
            "Impact Score": impact.get("impact_score"),
            "Risk": impact.get("risk_level"),
            "Simulation": simulation.get("simulation_name"),
        }

    @staticmethod
    def _expected_outcome(context: dict[str, Any], recommendation: dict[str, Any]) -> str:
        simulation = context.get("simulation") or {}
        financial = simulation.get("financial_analysis") or {}
        return (
            f"Expected outcome: {recommendation['Decision']} with "
            f"{_money(financial.get('Expected Annual Savings'))} annual savings, "
            f"{_money(financial.get('Migration Cost'))} migration cost, and "
            f"{financial.get('Payback Months', 0)} month payback."
        )

    @staticmethod
    def _persist(result: dict[str, Any]) -> None:
        AIReasoningRepository.save_history(
            {
                "id": result["id"],
                "organization_id": result["organization_id"],
                "question": result["question"],
                "reasoning": result["reasoning"],
                "recommendation": result["recommendation"]["Decision"],
                "confidence": result["confidence"]["Confidence"],
                "evidence": result["evidence"],
                "policies": result["policies"],
                "created_at": result["created_at"],
            }
        )
        EnterpriseIntelligenceService.log_intelligence_event(
            event_type="AI_REASONING_RUN",
            user_id=result.get("created_by") or "system",
            action="reason",
            resource_type="ai_reasoning",
            resource_id=result["id"],
            organization_id=result["organization_id"],
            details={
                "asset": result["asset"],
                "question": result["question"],
                "recommendation": result["recommendation"]["Decision"],
                "confidence": result["confidence"]["Confidence"],
            },
        )

    @staticmethod
    def _summary_row(reasoning: dict[str, Any]) -> dict[str, Any]:
        return {
            "Question": reasoning["question"],
            "Asset": reasoning["asset"],
            "Recommendation": reasoning["recommendation"]["Decision"],
            "Primary Action": reasoning["recommendation"]["Primary Action"],
            "Confidence": reasoning["confidence"]["Confidence"],
            "Expected Outcome": reasoning["expected_outcome"],
        }

    @staticmethod
    def _confidence_row(confidence: dict[str, Any]) -> dict[str, Any]:
        return {
            key: ", ".join(value) if isinstance(value, list) else value
            for key, value in confidence.items()
        }

    @staticmethod
    def _report_sections(reasoning: dict[str, Any]) -> list[tuple[str, list[str]]]:
        return [
            ("Recommendation", [reasoning["recommendation"]["Decision"], reasoning["recommendation"]["Why"]]),
            ("Why", [reasoning["explanation"]["Why"]]),
            ("Evidence", [f"{row['Evidence']}: {row['Value']}" for row in reasoning["evidence"]]),
            ("Policies Applied", [f"{row['Rule']}: {row['Action']}" for row in reasoning["policies"] if row["Matched"] == "Yes"] or ["No blocking policies matched."]),
            ("Alternatives", [f"{row['Alternative']}: {row['Recommendation']}" for row in reasoning["alternatives"]]),
            ("Confidence", [f"{key}: {value}" for key, value in AIReasoningService._confidence_row(reasoning["confidence"]).items()]),
            ("Expected Outcome", [reasoning["expected_outcome"]]),
        ]
