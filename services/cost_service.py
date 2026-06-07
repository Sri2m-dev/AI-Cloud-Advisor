"""
Cost Service
Unified Technology Spend Engine

Provides:
- Cloud Spend
- SaaS Spend
- License Spend
- Managed Services Spend
- Total Technology Spend
"""

from services.supabase_client import supabase


def _safe_sum(table_name, column="cost"):
    try:
        response = (
            supabase
            .table(table_name)
            .select(column)
            .execute()
        )

        total = sum(
            float(row.get(column, 0) or 0)
            for row in (response.data or [])
        )

        return round(total, 2)

    except Exception:
        return 0.0


def get_cloud_spend():
    """
    Current cloud spend from uploaded cloud costs.
    """
    try:
        response = (
            supabase
            .table("cost_usage_tracking")
            .select("cost")
            .execute()
        )

        total = sum(
            float(row.get("cost", 0) or 0)
            for row in (response.data or [])
        )

        return round(total, 2)

    except Exception:
        return 0.0


def get_saas_spend():
    return _safe_sum("saas_cost")


def get_license_spend():
    return _safe_sum("license_cost")


def get_managed_services_spend():
    return _safe_sum("managed_services_cost")


def get_total_technology_spend():
    return (
        get_cloud_spend()
        + get_saas_spend()
        + get_license_spend()
        + get_managed_services_spend()
    )


def get_spend_summary():
    cloud = get_cloud_spend()
    saas = get_saas_spend()
    license_cost = get_license_spend()
    managed_services = get_managed_services_spend()

    return {
        "cloud_spend": cloud,
        "saas_spend": saas,
        "license_spend": license_cost,
        "managed_services_spend": managed_services,
        "total_technology_spend": (
            cloud
            + saas
            + license_cost
            + managed_services
        )
    }