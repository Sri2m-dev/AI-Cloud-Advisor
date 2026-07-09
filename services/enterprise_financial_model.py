from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from services.application_portfolio_service import ApplicationPortfolioService
from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService


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


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _round(value: Any) -> float:
    return round(_safe_float(value), 2)


def _split_amount(amount: float, count: int) -> float:
    return amount / max(count, 1)


class EnterpriseFinancialModel:
    """
    E7.2.3 canonical financial model.

    This service is the first backend-only allocation engine for Nexora's
    business-to-technology hierarchy. It intentionally does not modify pages yet.
    """

    RECONCILED = "Reconciled"
    PARTIALLY_ALLOCATED = "Partially Allocated"
    VARIANCE_DETECTED = "Variance Detected"
    UNMAPPED = "Unmapped"

    @staticmethod
    def get_enterprise_summary() -> dict[str, Any]:
        model = EnterpriseFinancialModel._model()
        return model["enterprise_summary"]

    @staticmethod
    def get_business_unit_summary() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["business_units"]

    @staticmethod
    def get_capability_summary() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["capabilities"]

    @staticmethod
    def get_service_summary() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["services"]

    @staticmethod
    def get_process_summary() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["processes"]

    @staticmethod
    def get_application_summary() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["applications"]

    @staticmethod
    def get_technology_summary() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["technologies"]

    @staticmethod
    def get_reconciliation_status() -> dict[str, Any]:
        model = EnterpriseFinancialModel._model()
        summary = model["enterprise_summary"]
        return {
            "status": summary["status"],
            "enterprise_total": summary["enterprise_total"],
            "allocated_spend": summary["allocated_spend"],
            "unallocated_spend": summary["unallocated_spend"],
            "variance": summary["variance"],
            "variance_pct": summary["variance_pct"],
            "allocation_coverage": summary["allocation_coverage"],
            "business_coverage": summary["business_coverage"],
            "application_coverage": summary["application_coverage"],
            "technology_coverage": summary["technology_coverage"],
            "recommendation_coverage": summary["recommendation_coverage"],
            "variance_layers": [
                row for row in model["variance_report"]
                if row["status"] == EnterpriseFinancialModel.VARIANCE_DETECTED
            ],
            "generated_at": summary["generated_at"],
        }

    @staticmethod
    def get_unallocated_items() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["unallocated_items"]

    @staticmethod
    def get_variance_report() -> list[dict[str, Any]]:
        return EnterpriseFinancialModel._model()["variance_report"]

    @staticmethod
    def get_financial_tree() -> dict[str, Any]:
        return EnterpriseFinancialModel._model()["financial_tree"]

    @staticmethod
    def get_dashboard() -> dict[str, Any]:
        model = EnterpriseFinancialModel._model()
        return {
            "summary": model["enterprise_summary"],
            "business_units": model["business_units"],
            "capabilities": model["capabilities"],
            "services": model["services"],
            "processes": model["processes"],
            "applications": model["applications"],
            "technologies": model["technologies"],
            "unallocated_items": model["unallocated_items"],
            "variance_report": model["variance_report"],
            "financial_tree": model["financial_tree"],
        }

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def _model() -> dict[str, Any]:
        units = BusinessUnitService.get_business_units()
        capabilities = BusinessCapabilityService.get_capabilities()
        services = BusinessServiceService.get_business_services()
        processes = BusinessProcessService.get_business_processes()
        app_summary = ApplicationPortfolioService.get_application_summary()
        app_allocations = ApplicationPortfolioService.get_application_cost_allocation()
        unallocated_items = ApplicationPortfolioService.get_unallocated_spend_analysis()

        allocation_rows = EnterpriseFinancialModel._canonical_allocations(processes, services)
        allocated_spend = _round(sum(row["amount"] for row in allocation_rows))
        unallocated_spend = _round(sum(_safe_float(row.get("Amount")) for row in unallocated_items))
        enterprise_total = _round(allocated_spend + unallocated_spend)

        business_units = EnterpriseFinancialModel._business_unit_rollup(units, allocation_rows)
        capability_rows = EnterpriseFinancialModel._capability_rollup(capabilities, allocation_rows)
        service_rows = EnterpriseFinancialModel._service_rollup(services, allocation_rows)
        process_rows = EnterpriseFinancialModel._process_rollup(processes)
        application_rows = EnterpriseFinancialModel._application_rollup(allocation_rows, app_allocations)
        technology_rows = EnterpriseFinancialModel._technology_rollup(allocation_rows, unallocated_items)

        source_totals = {
            "business_units": sum(_safe_float(row.get("Allocated Spend")) for row in units),
            "capabilities": sum(_safe_float(row.get("monthly_cost")) for row in capabilities),
            "services": sum(_safe_float(row.get("monthly_cost")) for row in services),
            "processes": sum(_safe_float(row.get("monthly_cost")) for row in processes),
            "applications": _safe_float(app_summary.get("allocated_spend")),
            "technologies": sum(_safe_float(row.get("Amount")) for row in unallocated_items),
        }
        variance_report = EnterpriseFinancialModel._variance_report(allocated_spend, source_totals)
        variance = _round(max((abs(row["variance"]) for row in variance_report), default=0.0))
        variance_pct = _round((variance / allocated_spend * 100) if allocated_spend else 0.0)

        business_coverage = EnterpriseFinancialModel._coverage(len([row for row in business_units if row["allocated_spend"] > 0]), len(business_units))
        application_coverage = EnterpriseFinancialModel._coverage(len([row for row in application_rows if row["allocated_spend"] > 0]), len(application_rows))
        technology_coverage = EnterpriseFinancialModel._coverage(len([row for row in technology_rows if row["allocated_spend"] > 0]), len(technology_rows))
        recommendation_coverage = EnterpriseFinancialModel._coverage(
            sum(1 for row in process_rows if _safe_int(row.get("recommendations")) > 0),
            len(process_rows),
        )
        allocation_coverage = _round((allocated_spend / enterprise_total * 100) if enterprise_total else 0.0)
        potential_savings = _round(sum(_safe_float(row.get("optimization_opportunity")) for row in process_rows))
        forecast_spend = _round(sum(_safe_float(row.get("forecast_cost")) for row in process_rows) or allocated_spend * 1.08)
        budget = _round(enterprise_total * 1.10 if enterprise_total else 0.0)

        status = EnterpriseFinancialModel._status(
            allocated_spend=allocated_spend,
            unallocated_spend=unallocated_spend,
            variance_pct=variance_pct,
        )
        enterprise_summary = {
            "enterprise_total": enterprise_total,
            "allocated_spend": allocated_spend,
            "unallocated_spend": unallocated_spend,
            "variance": variance,
            "variance_pct": variance_pct,
            "allocation_coverage": allocation_coverage,
            "status": status,
            "business_coverage": business_coverage,
            "technology_coverage": technology_coverage,
            "application_coverage": application_coverage,
            "recommendation_coverage": recommendation_coverage,
            "potential_savings": potential_savings,
            "forecast_spend": forecast_spend,
            "budget": budget,
            "budget_variance": _round(forecast_spend - budget),
            "roi": _round((potential_savings / allocated_spend * 100) if allocated_spend else 0.0),
            "optimization_pct": _round((potential_savings / forecast_spend * 100) if forecast_spend else 0.0),
            "source_of_truth": "business_processes -> business_services -> application_portfolio",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        return {
            "enterprise_summary": enterprise_summary,
            "business_units": business_units,
            "capabilities": capability_rows,
            "services": service_rows,
            "processes": process_rows,
            "applications": application_rows,
            "technologies": technology_rows,
            "unallocated_items": EnterpriseFinancialModel._unallocated_items(unallocated_items),
            "variance_report": variance_report,
            "financial_tree": EnterpriseFinancialModel._financial_tree(business_units, capability_rows, service_rows, process_rows),
        }

    @staticmethod
    def _canonical_allocations(
        processes: list[dict[str, Any]],
        services: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        source_rows: list[dict[str, Any]]
        if processes:
            source_rows = processes
            source = "business_processes"
        else:
            source_rows = [
                {
                    "name": row.get("name"),
                    "business_unit": row.get("business_unit"),
                    "business_capability": row.get("business_capability"),
                    "business_service": row.get("name"),
                    "applications": row.get("applications"),
                    "technologies": row.get("technologies"),
                    "cloud_resources": row.get("cloud_resources"),
                    "monthly_cost": row.get("monthly_cost"),
                    "forecast_cost": row.get("forecast_cost"),
                    "optimization_opportunity": row.get("potential_savings"),
                    "recommendations": row.get("recommendations"),
                    "automation_opportunities": row.get("automation_candidates"),
                    "health_score": row.get("health_score"),
                    "risk_score": row.get("risk_score"),
                    "governance_score": row.get("governance_score"),
                    "source": row.get("source"),
                }
                for row in services
            ]
            source = "business_services"

        for row in source_rows:
            amount = _safe_float(row.get("monthly_cost"))
            applications = row.get("applications") or ["Unmapped Application"]
            technologies = row.get("technologies") or ["Unmapped Technology"]
            split_by_app = _split_amount(amount, len(applications))
            for application in applications:
                split_by_tech = _split_amount(split_by_app, len(technologies))
                for technology in technologies:
                    rows.append(
                        {
                            "enterprise": "Enterprise",
                            "business_unit": _normalize(row.get("business_unit"), "Unassigned"),
                            "business_capability": _normalize(row.get("business_capability"), "Unmapped Capability"),
                            "business_service": _normalize(row.get("business_service"), row.get("name") or "Unmapped Service"),
                            "business_process": _normalize(row.get("name"), "Unmapped Process"),
                            "application": _normalize(application, "Unmapped Application"),
                            "technology": _normalize(technology, "Unmapped Technology"),
                            "cloud_resource": _normalize(row.get("cloud_resource"), "Mapped Resource"),
                            "amount": split_by_tech,
                            "forecast_cost": _safe_float(row.get("forecast_cost")),
                            "optimization_opportunity": _safe_float(row.get("optimization_opportunity")),
                            "recommendations": _safe_int(row.get("recommendations")),
                            "automation_opportunities": _safe_int(row.get("automation_opportunities")),
                            "health_score": _safe_float(row.get("health_score")),
                            "risk_score": _safe_float(row.get("risk_score")),
                            "governance_score": _safe_float(row.get("governance_score")),
                            "source": source,
                        }
                    )
        return rows

    @staticmethod
    def _business_unit_rollup(
        units: list[dict[str, Any]],
        allocations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        grouped = EnterpriseFinancialModel._sum_by(allocations, "business_unit")
        unit_index = {_lower(row.get("Business Unit")): row for row in units}
        keys = sorted(set(grouped) | set(unit_index))
        return [
            {
                "business_unit": unit_index.get(key, {}).get("Business Unit") or grouped.get(key, {}).get("name") or key.title(),
                "allocated_spend": _round(grouped.get(key, {}).get("amount")),
                "source_spend": _round(unit_index.get(key, {}).get("Allocated Spend")),
                "variance": _round(_safe_float(grouped.get(key, {}).get("amount")) - _safe_float(unit_index.get(key, {}).get("Allocated Spend"))),
                "applications": _safe_int(unit_index.get(key, {}).get("Applications")) or len(grouped.get(key, {}).get("applications", set())),
                "business_services": _safe_int(unit_index.get(key, {}).get("Business Services")) or len(grouped.get(key, {}).get("services", set())),
                "status": EnterpriseFinancialModel._row_status(_safe_float(grouped.get(key, {}).get("amount")), _safe_float(unit_index.get(key, {}).get("Allocated Spend"))),
            }
            for key in keys
        ]

    @staticmethod
    def _capability_rollup(capabilities: list[dict[str, Any]], allocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped = EnterpriseFinancialModel._sum_by(allocations, "business_capability")
        source = {_lower(row.get("name")): row for row in capabilities}
        keys = sorted(set(grouped) | set(source))
        return [
            {
                "business_capability": source.get(key, {}).get("name") or grouped.get(key, {}).get("name") or key.title(),
                "business_unit": source.get(key, {}).get("business_unit") or grouped.get(key, {}).get("business_unit") or "Unassigned",
                "allocated_spend": _round(grouped.get(key, {}).get("amount")),
                "source_spend": _round(source.get(key, {}).get("monthly_cost")),
                "variance": _round(_safe_float(grouped.get(key, {}).get("amount")) - _safe_float(source.get(key, {}).get("monthly_cost"))),
                "applications": len(grouped.get(key, {}).get("applications", set())) or _safe_int(source.get(key, {}).get("applications")),
                "technologies": len(grouped.get(key, {}).get("technologies", set())),
                "status": EnterpriseFinancialModel._row_status(_safe_float(grouped.get(key, {}).get("amount")), _safe_float(source.get(key, {}).get("monthly_cost"))),
            }
            for key in keys
        ]

    @staticmethod
    def _service_rollup(services: list[dict[str, Any]], allocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped = EnterpriseFinancialModel._sum_by(allocations, "business_service")
        source = {_lower(row.get("name")): row for row in services}
        keys = sorted(set(grouped) | set(source))
        return [
            {
                "business_service": source.get(key, {}).get("name") or grouped.get(key, {}).get("name") or key.title(),
                "business_capability": source.get(key, {}).get("business_capability") or grouped.get(key, {}).get("business_capability") or "Unmapped Capability",
                "business_unit": source.get(key, {}).get("business_unit") or grouped.get(key, {}).get("business_unit") or "Unassigned",
                "allocated_spend": _round(grouped.get(key, {}).get("amount")),
                "source_spend": _round(source.get(key, {}).get("monthly_cost")),
                "variance": _round(_safe_float(grouped.get(key, {}).get("amount")) - _safe_float(source.get(key, {}).get("monthly_cost"))),
                "forecast_spend": _round(source.get(key, {}).get("forecast_cost")),
                "potential_savings": _round(source.get(key, {}).get("potential_savings")),
                "status": EnterpriseFinancialModel._row_status(_safe_float(grouped.get(key, {}).get("amount")), _safe_float(source.get(key, {}).get("monthly_cost"))),
            }
            for key in keys
        ]

    @staticmethod
    def _process_rollup(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "business_process": row.get("name"),
                "business_service": row.get("business_service"),
                "business_capability": row.get("business_capability"),
                "business_unit": row.get("business_unit"),
                "allocated_spend": _round(row.get("monthly_cost")),
                "forecast_cost": _round(row.get("forecast_cost")),
                "optimization_opportunity": _round(row.get("optimization_opportunity")),
                "applications": len(row.get("applications") or []),
                "technologies": len(row.get("technologies") or []),
                "recommendations": _safe_int(row.get("recommendations")),
                "automation_opportunities": _safe_int(row.get("automation_opportunities")),
                "status": EnterpriseFinancialModel.RECONCILED if _safe_float(row.get("monthly_cost")) else EnterpriseFinancialModel.UNMAPPED,
            }
            for row in processes
        ]

    @staticmethod
    def _application_rollup(allocations: list[dict[str, Any]], app_allocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped = EnterpriseFinancialModel._sum_by(allocations, "application")
        source = {_lower(row.get("App")): row for row in app_allocations}
        keys = sorted(set(grouped) | set(source))
        return [
            {
                "application": source.get(key, {}).get("App") or grouped.get(key, {}).get("name") or key.title(),
                "allocated_spend": _round(grouped.get(key, {}).get("amount")),
                "source_spend": _round(source.get(key, {}).get("Total")),
                "variance": _round(_safe_float(grouped.get(key, {}).get("amount")) - _safe_float(source.get(key, {}).get("Total"))),
                "technologies": len(grouped.get(key, {}).get("technologies", set())),
                "status": EnterpriseFinancialModel._row_status(_safe_float(grouped.get(key, {}).get("amount")), _safe_float(source.get(key, {}).get("Total"))),
            }
            for key in keys
        ]

    @staticmethod
    def _technology_rollup(allocations: list[dict[str, Any]], unallocated_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped = EnterpriseFinancialModel._sum_by(allocations, "technology")
        unallocated = defaultdict(float)
        for row in unallocated_items:
            unallocated[_lower(row.get("Technology") or row.get("Spend Source"))] += _safe_float(row.get("Amount"))
        keys = sorted(set(grouped) | set(unallocated))
        return [
            {
                "technology": grouped.get(key, {}).get("name") or key.title(),
                "allocated_spend": _round(grouped.get(key, {}).get("amount")),
                "unallocated_spend": _round(unallocated.get(key)),
                "total_spend": _round(_safe_float(grouped.get(key, {}).get("amount")) + unallocated.get(key, 0.0)),
                "applications": len(grouped.get(key, {}).get("applications", set())),
                "status": EnterpriseFinancialModel._technology_status(
                    _safe_float(grouped.get(key, {}).get("amount")),
                    unallocated.get(key, 0.0),
                ),
            }
            for key in keys
            if _safe_float(grouped.get(key, {}).get("amount")) > 0 or unallocated.get(key, 0.0) > 0
        ]

    @staticmethod
    def _sum_by(allocations: list[dict[str, Any]], key_name: str) -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in allocations:
            key = _lower(row.get(key_name))
            if not key:
                continue
            item = grouped.setdefault(
                key,
                {
                    "name": row.get(key_name),
                    "amount": 0.0,
                    "business_unit": row.get("business_unit"),
                    "business_capability": row.get("business_capability"),
                    "services": set(),
                    "applications": set(),
                    "technologies": set(),
                },
            )
            item["amount"] += _safe_float(row.get("amount"))
            item["services"].add(row.get("business_service"))
            item["applications"].add(row.get("application"))
            item["technologies"].add(row.get("technology"))
        return grouped

    @staticmethod
    def _variance_report(canonical: float, source_totals: dict[str, float]) -> list[dict[str, Any]]:
        rows = []
        for layer, source_total in source_totals.items():
            if layer == "technologies":
                continue
            variance = _round(_safe_float(source_total) - canonical)
            variance_pct = _round((variance / canonical * 100) if canonical else 0.0)
            rows.append(
                {
                    "layer": layer,
                    "canonical_allocated_spend": _round(canonical),
                    "source_spend": _round(source_total),
                    "variance": variance,
                    "variance_pct": variance_pct,
                    "status": EnterpriseFinancialModel.VARIANCE_DETECTED if abs(variance_pct) > 1 else EnterpriseFinancialModel.RECONCILED,
                }
            )
        return rows

    @staticmethod
    def _unallocated_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "spend_source": row.get("Spend Source"),
                "technology": row.get("Technology"),
                "amount": _round(row.get("Amount")),
                "status": row.get("Status") or EnterpriseFinancialModel.UNMAPPED,
                "reason": row.get("Reason") or "No canonical allocation path",
            }
            for row in rows
            if _safe_float(row.get("Amount")) > 0
        ]

    @staticmethod
    def _financial_tree(
        business_units: list[dict[str, Any]],
        capabilities: list[dict[str, Any]],
        services: list[dict[str, Any]],
        processes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "name": "Enterprise",
            "children": [
                {
                    "name": unit["business_unit"],
                    "allocated_spend": unit["allocated_spend"],
                    "status": unit["status"],
                    "children": [
                        {
                            "name": capability["business_capability"],
                            "allocated_spend": capability["allocated_spend"],
                            "status": capability["status"],
                            "children": [
                                {
                                    "name": service["business_service"],
                                    "allocated_spend": service["allocated_spend"],
                                    "status": service["status"],
                                    "children": [
                                        {
                                            "name": process["business_process"],
                                            "allocated_spend": process["allocated_spend"],
                                            "status": process["status"],
                                        }
                                        for process in processes
                                        if _lower(process.get("business_service")) == _lower(service.get("business_service"))
                                    ],
                                }
                                for service in services
                                if _lower(service.get("business_capability")) == _lower(capability.get("business_capability"))
                            ],
                        }
                        for capability in capabilities
                        if _lower(capability.get("business_unit")) == _lower(unit.get("business_unit"))
                    ],
                }
                for unit in business_units
            ],
        }

    @staticmethod
    def _coverage(numerator: int, denominator: int) -> float:
        return _round((numerator / denominator * 100) if denominator else 0.0)

    @staticmethod
    def _status(*, allocated_spend: float, unallocated_spend: float, variance_pct: float) -> str:
        if allocated_spend <= 0:
            return EnterpriseFinancialModel.UNMAPPED
        if abs(variance_pct) > 1:
            return EnterpriseFinancialModel.VARIANCE_DETECTED
        if unallocated_spend > 0:
            return EnterpriseFinancialModel.PARTIALLY_ALLOCATED
        return EnterpriseFinancialModel.RECONCILED

    @staticmethod
    def _row_status(allocated: float, source: float) -> str:
        if allocated <= 0 and source <= 0:
            return EnterpriseFinancialModel.UNMAPPED
        if allocated > 0 and source <= 0:
            return EnterpriseFinancialModel.PARTIALLY_ALLOCATED
        variance_pct = abs((allocated - source) / allocated * 100) if allocated else 0.0
        return EnterpriseFinancialModel.VARIANCE_DETECTED if variance_pct > 1 else EnterpriseFinancialModel.RECONCILED

    @staticmethod
    def _technology_status(allocated: float, unallocated: float) -> str:
        if allocated <= 0 and unallocated <= 0:
            return EnterpriseFinancialModel.UNMAPPED
        if allocated > 0 and unallocated > 0:
            return EnterpriseFinancialModel.PARTIALLY_ALLOCATED
        if unallocated > 0:
            return EnterpriseFinancialModel.UNMAPPED
        return EnterpriseFinancialModel.RECONCILED


