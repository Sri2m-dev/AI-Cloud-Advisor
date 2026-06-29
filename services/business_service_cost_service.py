from __future__ import annotations

from typing import Any

import pandas as pd

from repositories.business_service_cost_repository import BusinessServiceCostRepository


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


def _dedupe_pairs(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    deduped = []
    for left, right in rows:
        key = (_lower(left), _lower(right))
        if not left or not right or key in seen:
            continue
        seen.add(key)
        deduped.append((left, right))
    return deduped


class BusinessServiceCostService:
    @staticmethod
    def get_business_services() -> list[dict[str, Any]]:
        return BusinessServiceCostRepository.get_business_services()

    @staticmethod
    def get_application_mappings() -> list[dict[str, Any]]:
        return BusinessServiceCostRepository.get_application_mappings()

    @staticmethod
    def get_application_spend() -> list[dict[str, Any]]:
        return BusinessServiceCostRepository.get_application_spend()

    @staticmethod
    def get_technology_inventory() -> list[dict[str, Any]]:
        return BusinessServiceCostRepository.get_technology_inventory()

    @staticmethod
    def get_service_relationships() -> list[dict[str, Any]]:
        return BusinessServiceCostRepository.get_service_relationships()

    @staticmethod
    def get_application_spend_mapping() -> list[dict[str, Any]]:
        return BusinessServiceCostRepository.get_application_spend_mapping()

    @staticmethod
    def _service_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "service_name",
                "business_service_name",
                "name",
                "service",
                default="Unknown Service",
            )
        )

    @staticmethod
    def _application_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "application_name",
                "application",
                "app_name",
                "registry_application",
                "name",
                default="Unknown Application",
            )
        )

    @staticmethod
    def _technology_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "technology_name",
                "technology",
                "tool_name",
                "product",
                "vendor_name",
                "provider",
                "service_name",
                default="Unknown Technology",
            )
        )

    @staticmethod
    def _owner(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "service_owner",
                "owner",
                "business_owner",
                "application_owner",
                default="Unassigned",
            )
        )

    @staticmethod
    def _annual_cost(row: dict[str, Any]) -> float:
        annual_cost = _safe_float(
            _first_existing(
                row,
                "annual_cost",
                "annual_spend",
                "annual_service_cost",
                "service_cost",
                "total_spend",
                "total_cost",
                "cost",
                "amount",
                default=0,
            )
        )
        if annual_cost:
            return annual_cost
        return _safe_float(_first_existing(row, "monthly_cost", "monthly_spend", default=0)) * 12

    @staticmethod
    def _savings_value(row: dict[str, Any]) -> float:
        return _safe_float(
            _first_existing(
                row,
                "optimization_potential",
                "savings_potential",
                "estimated_savings",
                "waste",
                "estimated_waste",
                default=0,
            )
        )

    @staticmethod
    def _service_lookup() -> dict[str, dict[str, Any]]:
        return {
            _lower(BusinessServiceCostService._service_name(row)): row
            for row in BusinessServiceCostService.get_business_services()
        }

    @staticmethod
    def _application_spend_lookup() -> dict[str, float]:
        spend: dict[str, float] = {}
        for row in BusinessServiceCostService.get_application_spend():
            application = BusinessServiceCostService._application_name(row)
            spend[_lower(application)] = spend.get(_lower(application), 0.0) + BusinessServiceCostService._annual_cost(row)
        return spend

    @staticmethod
    def _technology_cost_lookup() -> dict[str, float]:
        costs: dict[str, float] = {}
        for row in BusinessServiceCostService.get_technology_inventory():
            technology = BusinessServiceCostService._technology_name(row)
            costs[_lower(technology)] = costs.get(_lower(technology), 0.0) + BusinessServiceCostService._annual_cost(row)
        return costs

    @staticmethod
    def _technology_display_lookup() -> dict[str, str]:
        return {
            _lower(BusinessServiceCostService._technology_name(row)): BusinessServiceCostService._technology_name(row)
            for row in BusinessServiceCostService.get_technology_inventory()
        }

    @staticmethod
    def _service_application_pairs() -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        service_lookup = BusinessServiceCostService._service_lookup()

        for row in BusinessServiceCostService.get_service_relationships():
            source = _normalize(_first_existing(row, "source_name", "source", "from_name", "business_service_name", "service_name"))
            target = _normalize(_first_existing(row, "target_name", "target", "to_name", "application_name", "dependent_name"))
            source_type = _lower(_first_existing(row, "source_type", "from_type", default=""))
            target_type = _lower(_first_existing(row, "target_type", "to_type", default=""))

            if source and target and (
                source_type == "business service"
                or target_type == "application"
                or _lower(source) in service_lookup
            ):
                pairs.append((source, target))

        for row in BusinessServiceCostService.get_application_mappings():
            application = BusinessServiceCostService._application_name(row)
            service = _normalize(_first_existing(row, "business_service_name", "service_name", "service", default=""))
            if not service and len(service_lookup) == 1:
                service = BusinessServiceCostService._service_name(next(iter(service_lookup.values())))
            if service and application:
                pairs.append((service, application))

        return _dedupe_pairs(pairs)

    @staticmethod
    def _application_technology_pairs() -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []

        for row in BusinessServiceCostService.get_service_relationships():
            source = _normalize(_first_existing(row, "source_name", "source", "from_name"))
            target = _normalize(_first_existing(row, "target_name", "target", "to_name", "technology_name", "dependent_name"))
            source_type = _lower(_first_existing(row, "source_type", "from_type", default=""))
            target_type = _lower(_first_existing(row, "target_type", "to_type", default=""))

            if source and target and (
                source_type == "application"
                or target_type == "technology"
                or target_type in {"platform", "vendor", "managed service"}
            ):
                pairs.append((source, target))

        for row in BusinessServiceCostService.get_application_mappings():
            application = BusinessServiceCostService._application_name(row)
            technology = BusinessServiceCostService._technology_name(row)
            if application and technology:
                pairs.append((application, technology))

        for row in BusinessServiceCostService.get_application_mappings():
            application = BusinessServiceCostService._application_name(row)
            technology = _normalize(_first_existing(row, "cloud", "platform", default=""))
            if application and technology:
                pairs.append((application, technology))

        return _dedupe_pairs(pairs)

    @staticmethod
    def get_cost_allocations() -> list[dict[str, Any]]:
        services = BusinessServiceCostService.get_business_services()
        service_application_pairs = BusinessServiceCostService._service_application_pairs()
        application_technology_pairs = BusinessServiceCostService._application_technology_pairs()
        app_spend = BusinessServiceCostService._application_spend_lookup()
        technology_cost = BusinessServiceCostService._technology_cost_lookup()

        applications_by_service: dict[str, set[str]] = {}
        for service, application in service_application_pairs:
            applications_by_service.setdefault(_lower(service), set()).add(application)

        technologies_by_application: dict[str, set[str]] = {}
        for application, technology in application_technology_pairs:
            technologies_by_application.setdefault(_lower(application), set()).add(technology)

        allocations: list[dict[str, Any]] = []
        for row in services:
            service_name = BusinessServiceCostService._service_name(row)
            applications = applications_by_service.get(_lower(service_name), set())
            technologies = {
                technology
                for application in applications
                for technology in technologies_by_application.get(_lower(application), set())
            }

            application_cost = sum(app_spend.get(_lower(application), 0.0) for application in applications)
            technology_exposure = sum(technology_cost.get(_lower(technology), 0.0) for technology in technologies)
            annual_cost = BusinessServiceCostService._annual_cost(row)
            optimization_potential = (
                BusinessServiceCostService._savings_value(row)
                + application_cost * 0.05
                + technology_exposure * 0.05
            )

            allocations.append(
                {
                    "service_name": service_name,
                    "annual_cost": annual_cost,
                    "application_cost": application_cost,
                    "technology_cost": technology_exposure,
                    "total_exposure": application_cost + technology_exposure,
                    "owner": BusinessServiceCostService._owner(row),
                    "criticality": _normalize(_first_existing(row, "criticality", "service_criticality", default="Standard")),
                    "optimization_potential": optimization_potential,
                    "applications": sorted(applications),
                    "technologies": sorted(technologies),
                }
            )

        return sorted(allocations, key=lambda item: item["total_exposure"], reverse=True)

    @staticmethod
    def get_spend_attribution() -> list[dict[str, Any]]:
        technology_cost = BusinessServiceCostService._technology_cost_lookup()
        rows: list[dict[str, Any]] = []

        for allocation in BusinessServiceCostService.get_cost_allocations():
            for technology in allocation["technologies"]:
                rows.append(
                    {
                        "Business Service": allocation["service_name"],
                        "Technology": technology,
                        "Annual Cost": technology_cost.get(_lower(technology), 0.0),
                    }
                )

        return sorted(rows, key=lambda row: row["Annual Cost"], reverse=True)

    @staticmethod
    def get_unallocated_spend() -> list[dict[str, Any]]:
        allocated_technologies = {
            _lower(row["Technology"])
            for row in BusinessServiceCostService.get_spend_attribution()
        }
        display_lookup = BusinessServiceCostService._technology_display_lookup()
        technology_cost = BusinessServiceCostService._technology_cost_lookup()

        rows = []
        for key, cost in technology_cost.items():
            if key in allocated_technologies:
                continue
            rows.append(
                {
                    "Technology": display_lookup.get(key, key.title()),
                    "Annual Cost": cost,
                    "Reason Not Allocated": "No application mapping",
                }
            )
        return sorted(rows, key=lambda row: row["Annual Cost"], reverse=True)

    @staticmethod
    def get_kpis() -> dict[str, Any]:
        allocations = BusinessServiceCostService.get_cost_allocations()
        unallocated = BusinessServiceCostService.get_unallocated_spend()

        allocated_spend = sum(row["annual_cost"] for row in allocations)
        unallocated_spend = sum(row["Annual Cost"] for row in unallocated)
        critical_services = len(
            [
                row for row in allocations
                if _lower(row["criticality"]) in {"critical", "tier 1", "tier1"}
            ]
        )
        optimization_potential = sum(row["optimization_potential"] for row in allocations)

        return {
            "business_services": len(allocations),
            "allocated_spend": allocated_spend,
            "unallocated_spend": unallocated_spend,
            "critical_services": critical_services,
            "optimization_potential": optimization_potential,
        }

    @staticmethod
    def get_cost_waterfall_edges() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        service_application_pairs = BusinessServiceCostService._service_application_pairs()
        application_technology_pairs = BusinessServiceCostService._application_technology_pairs()
        app_spend = BusinessServiceCostService._application_spend_lookup()
        technology_cost = BusinessServiceCostService._technology_cost_lookup()

        for service, application in service_application_pairs:
            rows.append(
                {
                    "Source": service,
                    "Target": application,
                    "Value": max(app_spend.get(_lower(application), 1.0), 1.0),
                }
            )

        for application, technology in application_technology_pairs:
            rows.append(
                {
                    "Source": application,
                    "Target": technology,
                    "Value": max(technology_cost.get(_lower(technology), 1.0), 1.0),
                }
            )

        return rows

    @staticmethod
    def get_executive_narrative() -> str:
        allocations = BusinessServiceCostService.get_cost_allocations()
        attribution = BusinessServiceCostService.get_spend_attribution()
        unallocated = BusinessServiceCostService.get_unallocated_spend()

        if not allocations:
            return "Business service cost allocation is ready, but no business service spend is currently available."

        allocated_total = sum(row["annual_cost"] for row in allocations)
        top_service = max(allocations, key=lambda row: row["annual_cost"])
        service_share = (
            top_service["annual_cost"] / allocated_total * 100
            if allocated_total
            else 0
        )

        total_technology_exposure = sum(row["Annual Cost"] for row in attribution)
        top_technology = max(attribution, key=lambda row: row["Annual Cost"]) if attribution else None
        top_technology_share = (
            top_technology["Annual Cost"] / total_technology_exposure * 100
            if top_technology and total_technology_exposure
            else 0
        )

        secondary = sorted(attribution, key=lambda row: row["Annual Cost"], reverse=True)[1:3]
        secondary_share = (
            sum(row["Annual Cost"] for row in secondary) / total_technology_exposure * 100
            if total_technology_exposure
            else 0
        )
        secondary_names = " and ".join(row["Technology"] for row in secondary) or "No secondary platforms"
        leakage_sentence = (
            "No spend leakage identified."
            if not unallocated or not sum(row["Annual Cost"] for row in unallocated)
            else f"${sum(row['Annual Cost'] for row in unallocated):,.0f} remains unallocated and requires application mapping."
        )

        technology_sentence = (
            f"{top_technology['Technology']} contributes {top_technology_share:.0f}% of total technology exposure. "
            if top_technology
            else ""
        )

        return (
            f"{top_service['service_name']} represents {service_share:.0f}% of allocated business service spend. "
            f"{technology_sentence}{secondary_names} contribute {secondary_share:.0f}%. "
            f"{leakage_sentence}"
        )

    @staticmethod
    def allocations_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceCostService.get_cost_allocations())

    @staticmethod
    def spend_attribution_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceCostService.get_spend_attribution())

    @staticmethod
    def unallocated_spend_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceCostService.get_unallocated_spend())

    @staticmethod
    def cost_waterfall_dataframe() -> pd.DataFrame:
        return pd.DataFrame(BusinessServiceCostService.get_cost_waterfall_edges())
