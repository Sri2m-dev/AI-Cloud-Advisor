from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

import pandas as pd

from config import DEFAULT_ORG_ID
from repositories.ai_governance_repository import AIGovernanceRepository
from services.supabase_client import supabase


AI_TOOL_FALLBACK = [
    {
        "technology_name": "ChatGPT Enterprise",
        "vendor_name": "OpenAI",
        "annual_cost": 12000,
        "owner_department": "Engineering",
        "technology_type": "AI",
        "account_type": "Enterprise",
        "status": "ACTIVE",
    },
    {
        "technology_name": "Copilot",
        "vendor_name": "Microsoft",
        "annual_cost": 9000,
        "owner_department": "Engineering",
        "technology_type": "AI",
        "account_type": "Enterprise",
        "status": "ACTIVE",
    },
    {
        "technology_name": "Claude",
        "vendor_name": "Anthropic",
        "annual_cost": 6000,
        "owner_department": "Operations",
        "technology_type": "AI",
        "account_type": "Team",
        "status": "ACTIVE",
    },
    {
        "technology_name": "Gemini",
        "vendor_name": "Google",
        "annual_cost": 5000,
        "owner_department": "Finance",
        "technology_type": "AI",
        "account_type": "Team",
        "status": "ACTIVE",
    },
    {
        "technology_name": "Cursor",
        "vendor_name": "Cursor",
        "annual_cost": 3000,
        "owner_department": "Engineering",
        "technology_type": "AI",
        "account_type": "Team",
        "status": "ACTIVE",
    },
]


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _lower(value: Any) -> str:
    return _normalize(value).lower()


def _first_existing(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _tool_name(row: dict[str, Any]) -> str:
    return _normalize(
        _first_existing(row, "technology_name", "tool", "application_name", "name", default="Unknown AI Tool"),
        "Unknown AI Tool",
    )


def _vendor_name(row: dict[str, Any]) -> str:
    return _normalize(
        _first_existing(row, "vendor_name", "vendor", "provider", "technology_name", default="Unknown"),
        "Unknown",
    )


def _owner(row: dict[str, Any]) -> str:
    return _normalize(
        _first_existing(row, "owner_department", "department", "business_owner", "owner", default="Unknown"),
        "Unknown",
    )


def _spend(row: dict[str, Any]) -> float:
    return _safe_float(
        _first_existing(
            row,
            "annual_cost",
            "annual_spend",
            "total_spend",
            "yearly_cost",
            "cost",
            "amount",
            "spend",
            default=0,
        )
    )


def _is_enterprise(row: dict[str, Any]) -> bool:
    fields = (
        _tool_name(row),
        _first_existing(row, "license_type", "plan", "account_type", "edition", default=""),
        _first_existing(row, "governance_status", "status", default=""),
    )
    text = " ".join(str(value or "") for value in fields).lower()
    return "enterprise" in text or "governed" in text


def _is_personal_account(row: dict[str, Any]) -> bool:
    email = _lower(_first_existing(row, "email", "user_email", "account", "account_email", default=""))
    account_type = _lower(_first_existing(row, "account_type", "license_type", "plan", default=""))
    return "personal" in account_type or email.endswith("@gmail.com") or email.endswith("@outlook.com")


class AIGovernanceService:
    @staticmethod
    def get_ai_tools() -> list[dict[str, Any]]:
        rows = AIGovernanceRepository.get_ai_tools()
        return rows or [dict(row) for row in AI_TOOL_FALLBACK]

    @staticmethod
    def get_ai_spend() -> float:
        return sum(_spend(row) for row in AIGovernanceService.get_ai_tools())

    @staticmethod
    def get_ai_vendors() -> list[str]:
        vendors = {_vendor_name(row) for row in AIGovernanceService.get_ai_tools()}
        return sorted(vendor for vendor in vendors if vendor != "Unknown")

    @staticmethod
    def get_ai_license_summary() -> dict[str, Any]:
        tools = AIGovernanceService.get_ai_tools()
        return {
            "total_ai_spend": AIGovernanceService.get_ai_spend(),
            "ai_vendors": AIGovernanceService.get_ai_vendors(),
            "ai_tools": len({_tool_name(row) for row in tools}),
            "duplicate_ai_platforms": ["ChatGPT", "Claude", "Gemini"],
            "consolidation_note": (
                "ChatGPT, Claude and Gemini perform similar functions and are potential consolidation candidates."
            ),
        }

    @staticmethod
    def _department_tool_counts() -> dict[str, set[str]]:
        departments: dict[str, set[str]] = {}
        for row in AIGovernanceService.get_ai_tools():
            departments.setdefault(_owner(row), set()).add(_tool_name(row))
        return departments

    @staticmethod
    def get_ai_risk_summary() -> list[dict[str, str]]:
        tools = AIGovernanceService.get_ai_tools()
        has_personal_usage = any(_is_personal_account(row) for row in tools)
        has_unmanaged_usage = has_personal_usage or any(not _is_enterprise(row) for row in tools)
        duplicate_departments = [
            department
            for department, department_tools in AIGovernanceService._department_tool_counts().items()
            if len(department_tools) > 1
        ]
        has_enterprise = any(_is_enterprise(row) for row in tools)

        risks = [
            {
                "Risk": "Duplicate AI Tools",
                "Severity": "Medium" if duplicate_departments or len(tools) > 2 else "Low",
            },
            {
                "Risk": "AI Spend Growth",
                "Severity": "Medium" if AIGovernanceService.get_ai_spend() >= 25000 else "Low",
            },
            {
                "Risk": "Unmanaged AI Usage",
                "Severity": "Critical" if has_unmanaged_usage else "Low",
            },
        ]

        if has_enterprise:
            risks.append({"Risk": "Enterprise AI", "Severity": "Low"})

        return risks[:3]

    @staticmethod
    def get_ai_governance_overview() -> list[dict[str, Any]]:
        return [
            {
                "Tool": _tool_name(row),
                "Cost": _spend(row),
                "Owner": _owner(row),
                "Risk": "Low" if _is_enterprise(row) or _tool_name(row).lower() in {"cursor", "copilot"} else "Medium",
            }
            for row in sorted(AIGovernanceService.get_ai_tools(), key=_spend, reverse=True)
        ]

    @staticmethod
    def get_optimization_recommendations() -> list[dict[str, Any]]:
        return [
            {
                "title": "Consolidate Claude into ChatGPT",
                "description": "Reduce duplicate conversational AI platforms by consolidating Claude usage into ChatGPT Enterprise.",
                "estimated_savings": 6000,
                "priority": "medium",
                "resource": "Claude",
            },
            {
                "title": "Remove inactive Copilot licenses",
                "description": "Reclaim inactive Copilot seats from users without recent activity.",
                "estimated_savings": 2000,
                "priority": "medium",
                "resource": "Copilot",
            },
            {
                "title": "Reduce Gemini seats",
                "description": "Right-size Gemini seats where Finance usage overlaps with governed enterprise AI tooling.",
                "estimated_savings": 1000,
                "priority": "low",
                "resource": "Gemini",
            },
        ]

    @staticmethod
    def get_optimization_potential() -> float:
        return sum(row["estimated_savings"] for row in AIGovernanceService.get_optimization_recommendations())

    @staticmethod
    def save_optimization_recommendations(username: str | None = None, org_id: str = DEFAULT_ORG_ID) -> int:
        recommendations = AIGovernanceService.get_optimization_recommendations()
        if username:
            from services.recommendation_service import create_recommendation

            for recommendation in recommendations:
                create_recommendation(
                    username=username,
                    category="AI Optimization",
                    title=recommendation["title"],
                    description=recommendation["description"],
                    source="ai_governance",
                    resource=recommendation["resource"],
                    estimated_savings=recommendation["estimated_savings"],
                    priority=recommendation["priority"],
                    confidence_score=0.82,
                    rationale="Duplicate AI capabilities and inactive licenses create avoidable subscription cost.",
                    effort_level="low",
                    action_steps=[
                        "Confirm business owner and active usage.",
                        "Approve license consolidation or seat reduction.",
                        "Track realized savings in the recommendation workflow.",
                    ],
                )
            return len(recommendations)

        rows = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for recommendation in recommendations:
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "org_id": org_id,
                    "category": "AI Optimization",
                    "type": "AI_OPTIMIZATION",
                    "title": recommendation["title"],
                    "message": recommendation["description"],
                    "description": recommendation["description"],
                    "impact": recommendation["priority"].upper(),
                    "priority": recommendation["priority"],
                    "estimated_savings": recommendation["estimated_savings"],
                    "savings_monthly": recommendation["estimated_savings"],
                    "service": recommendation["resource"],
                    "resource": recommendation["resource"],
                    "source": "ai_governance",
                    "status": "new",
                    "created_at": now,
                }
            )
        try:
            supabase.table("recommendations").upsert(rows, on_conflict="org_id,message").execute()
        except Exception:
            return 0
        return len(rows)

    @staticmethod
    def governance_overview_dataframe() -> pd.DataFrame:
        return pd.DataFrame(AIGovernanceService.get_ai_governance_overview())

    @staticmethod
    def risk_summary_dataframe() -> pd.DataFrame:
        return pd.DataFrame(AIGovernanceService.get_ai_risk_summary())

    @staticmethod
    def optimization_recommendations_dataframe() -> pd.DataFrame:
        return pd.DataFrame(AIGovernanceService.get_optimization_recommendations())
