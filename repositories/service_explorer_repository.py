from services.supabase_client import supabase
import streamlit as st


class ServiceExplorerRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_service_classification():
        response = (
            supabase
            .table("mart_service_classification")
            .select("*")
            .order("total_cost", desc=True)
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_top_services(limit=15):
        response = (
            supabase
            .table("mart_service_classification")
            .select("*")
            .order("total_cost", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_optimization_opportunities():
        response = (
            supabase
            .table("mart_optimization_opportunities")
            .select("*")
            .order("total_cost", desc=True)
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_recommendations():
        response = (
            supabase
            .table("mart_recommendations")
            .select("*")
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_anomalies():
        response = (
            supabase
            .table("mart_cost_anomalies")
            .select("*")
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_anomalies():
        response = (
            supabase
            .table("mart_cost_anomalies")
            .select("*")
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_ai_recommendations():
        response = (
            supabase
            .table("mart_ai_recommendations")
            .select("*")
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_kpis():

        services = (
            ServiceExplorerRepository
            .get_service_classification()
        )

        optimizations = (
            ServiceExplorerRepository
            .get_optimization_opportunities()
        )

        anomalies = (
            ServiceExplorerRepository
            .get_cost_anomalies()
        )

        if not services:
            return {
                "total_services": 0,
                "critical_services": 0,
                "total_spend": 0,
                "optimization_candidates": 0,
                "active_anomalies": 0,
            }

        total_services = len(services)

        critical_services = len(
            [
                s
                for s in services
                if str(
                    s.get(
                        "criticality",
                        ""
                    )
                ).lower() == "high"
            ]
        )

        total_spend = sum(
            float(
                s.get(
                    "total_cost",
                    0
                ) or 0
            )
            for s in services
        )

        optimization_candidates = len(
            optimizations
        )

        active_anomalies = len(
            [
                a
                for a in anomalies
                if str(
                    a.get(
                        "anomaly_status",
                        ""
                    )
                ).lower() != "normal"
            ]
        )

        return {
            "total_services": total_services,
            "critical_services": critical_services,
            "total_spend": total_spend,
            "optimization_candidates": optimization_candidates,
            "active_anomalies": active_anomalies,
        }