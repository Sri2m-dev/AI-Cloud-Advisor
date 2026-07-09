from __future__ import annotations

from typing import Any

import streamlit as st

from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.platform.formatting import safe_float, safe_int


def _safe_call(fn, fallback):
    try:
        return fn() or fallback
    except Exception:
        return fallback


class BusinessContextService:
    """Shared business architecture context used by certified workspaces."""

    @staticmethod
    def get_context(extra: dict[str, Any] | None = None) -> dict[str, Any]:
        context = dict(BusinessContextService._base_context())
        if extra:
            context.update(extra)
        return context

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def _base_context() -> dict[str, Any]:
        unit_summary = _safe_call(BusinessUnitService.get_summary, {})
        capability_summary = _safe_call(BusinessCapabilityService.get_capability_summary, {})
        service_summary = _safe_call(BusinessServiceService.get_service_summary, {})
        process_summary = _safe_call(BusinessProcessService.get_process_summary, {})
        return {
            "business_units": safe_int(unit_summary.get("business_units") or unit_summary.get("total_business_units")),
            "capabilities": safe_int(capability_summary.get("capabilities") or capability_summary.get("total_capabilities")),
            "business_services": safe_int(service_summary.get("business_services") or service_summary.get("total_services")),
            "business_processes": safe_int(process_summary.get("business_processes") or process_summary.get("total_processes")),
            "applications": safe_int(service_summary.get("applications")),
            "technologies": safe_int(service_summary.get("technologies")),
            "mapping_coverage": safe_float(
                service_summary.get("mapping_coverage")
                or capability_summary.get("mapping_coverage")
                or unit_summary.get("mapping_coverage")
            ),
        }

    @staticmethod
    def relationship_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
        rows = [
            ("Business Units", "business_units"),
            ("Capabilities", "capabilities"),
            ("Business Services", "business_services"),
            ("Business Processes", "business_processes"),
            ("Applications", "applications"),
            ("Technologies", "technologies"),
        ]
        return [{"Layer": label, "Count": safe_int(context.get(key))} for label, key in rows]


