"""Supabase queries used by the Executive Dashboard."""

from __future__ import annotations

import streamlit as st

from services.supabase_client import supabase


def _require_organization_id(organization_id: str) -> str:
    value = str(organization_id or "").strip()
    if not value:
        raise ValueError("organization_id is required for dashboard queries")
    return value


class DashboardRepository:

    @staticmethod
    @st.cache_data(ttl=0, show_spinner=False)
    def fetch_recommendations(organization_id: str):
        organization_id = _require_organization_id(organization_id)

        try:
            response = (
                supabase
                .table("recommendations")
                .select("*")
                .eq("org_id", organization_id)
                .execute()
            )

            data = response.data or []

            print("\n" + "=" * 80)
            print("RECOMMENDATIONS QUERY")
            print(f"Rows Returned: {len(data)}")

            if data:
                print("First Record:")
                print(data[0])

            print("=" * 80)

            return data

        except Exception as e:
            print("\n" + "=" * 80)
            print("RECOMMENDATIONS ERROR")
            print(type(e).__name__)
            print(str(e))
            print("=" * 80)

            return []

    @staticmethod
    @st.cache_data(ttl=0, show_spinner=False)
    def fetch_cost_rows(organization_id: str):
        _require_organization_id(organization_id)

        try:
            # Cost rows are intentionally read as an enterprise-wide snapshot here.
            response = (
                supabase
                .table("unified_cloud_costs")
                .select("*", count="exact")
                .execute()
            )

            print("\n" + "=" * 80)
            print("UNIFIED CLOUD COSTS")
            print(f"Count: {response.count}")
            print(f"Rows Returned: {len(response.data or [])}")

            if response.data:
                print("First Record:")
                print(response.data[0])

            print("=" * 80)

            return response.data or []

        except Exception as e:
            print("\n" + "=" * 80)
            print("UNIFIED CLOUD COSTS ERROR")
            print(type(e).__name__)
            print(str(e))
            print("=" * 80)

            return []

    @staticmethod
    @st.cache_data(ttl=0, show_spinner=False)
    def fetch_approval_queue(organization_id: str):
        _require_organization_id(organization_id)

        try:
            # Approval queue is currently consumed as a global governance snapshot.
            response = (
                supabase
                .table("approval_queue")
                .select("*")
                .execute()
            )

            data = response.data or []

            print("\n" + "=" * 80)
            print("APPROVAL QUEUE QUERY")
            print(f"Rows Returned: {len(data)}")

            if data:
                print("First Record:")
                print(data[0])

            print("=" * 80)

            return data

        except Exception as e:
            print("\n" + "=" * 80)
            print("APPROVAL QUEUE ERROR")
            print(type(e).__name__)
            print(str(e))
            print("=" * 80)

            return []

    @staticmethod
    @st.cache_data(ttl=0, show_spinner=False)
    def fetch_anomalies(organization_id: str):
        _require_organization_id(organization_id)

        try:
            # Anomaly view is currently consumed as a global risk snapshot.
            response = (
                supabase
                .table("cost_anomaly_view")
                .select("*")
                .execute()
            )

            data = response.data or []

            print("\n" + "=" * 80)
            print("ANOMALIES QUERY")
            print(f"Rows Returned: {len(data)}")

            if data:
                print("First Record:")
                print(data[0])

            print("=" * 80)

            return data

        except Exception as e:
            print("\n" + "=" * 80)
            print("ANOMALIES ERROR")
            print(type(e).__name__)
            print(str(e))
            print("=" * 80)

            return []
