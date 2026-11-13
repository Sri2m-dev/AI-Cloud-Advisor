import os

import streamlit as st

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.contracts import EntityType
from repositories.enterprise_registry_source import CanonicalDataFabricRegistrySource
from services.supabase_client import supabase


class PortfolioUnavailable(RuntimeError):
    """Canonical portfolio could not be read; this is not an empty portfolio."""


class ApplicationPortfolioRepository:
    @staticmethod
    def _fetch_table(table_name: str):
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    def get_applications(context=None, *, source=None):
        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("Verified authenticated tenant context is required")
        try:
            if source is None:
                url = os.getenv("SUPABASE_URL", "")
                key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
                if not url or not key:
                    raise PortfolioUnavailable("Canonical Data Fabric reader is not configured")
                source = CanonicalDataFabricRegistrySource.from_supabase(url, key)
            rows = []
            for entity in source.entities(context.fabric_context):
                context.fabric_context.assert_record_matches(entity, "portfolio application")
                if entity.entity_type != EntityType.APPLICATION:
                    continue
                rows.append(
                    {
                        "id": entity.canonical_id,
                        "app_name": entity.display_name or entity.name,
                        "owner_name": entity.ownership.owner_name if entity.ownership else None,
                        "lifecycle_status": entity.lifecycle_status,
                        "source_system": entity.source_system,
                        "source_identifier": entity.source_identifier,
                    }
                )
            return sorted(rows, key=lambda row: row["id"])
        except PortfolioUnavailable:
            raise
        except Exception as exc:
            raise PortfolioUnavailable("Canonical application inventory is unavailable") from exc

    @staticmethod
    def get_application_spend(context=None):
        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("Verified authenticated tenant context is required")
        return {
            "status": "UNKNOWN",
            "rows": [],
            "reason": (
                "No canonical tenant-scoped financial reader binds spend to application "
                "canonical_id with authoritative attribution, currency, period "
                "and source provenance. "
                "tenant_cloud_account_posture supports cloud accounts only."
            ),
        }

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_dependencies():
        return ApplicationPortfolioRepository._fetch_table("business_service_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_risks():
        return ApplicationPortfolioRepository._fetch_table("technology_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_unallocated_spend():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend_mapping():
        return []
