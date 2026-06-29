from services.supabase_client import supabase
import streamlit as st


def _spend_value(row, new_key, old_key):
    return float(
        row.get(
            new_key,
            row.get(old_key, 0)
        )
        or 0
    )


class TechnologySpendRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_enterprise_spend_breakdown():

        response = (
            supabase
            .table("mart_enterprise_spend_v2")
            .select("*")
            .execute()
        )

        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_managed_services_cost():

        response = (
            supabase
            .table("managed_services_cost")
            .select("*")
            .execute()
        )

        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_saas_cost():

        response = (
            supabase
            .table("saas_cost")
            .select("*")
            .execute()
        )

        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_latest_summary():

        data = (
            TechnologySpendRepository
            .get_enterprise_spend_breakdown()
        )

        if data:
            return data[0]

        return {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_kpis():

        summary = (
            TechnologySpendRepository
            .get_latest_summary()
        )

        cloud_spend = _spend_value(summary, "cloud_spend", "cloud_cost")
        saas_spend = _spend_value(summary, "saas_spend", "saas_cost")
        msp_spend = _spend_value(summary, "msp_spend", "msp_cost")
        license_spend = _spend_value(summary, "license_spend", "license_cost")

        return {
            "cloud_cost": cloud_spend,
            "saas_cost": saas_spend,
            "msp_cost": msp_spend,
            "license_cost": license_spend,
            "total_spend": (
                cloud_spend
                + saas_spend
                + msp_spend
                + license_spend
            ),
        }
