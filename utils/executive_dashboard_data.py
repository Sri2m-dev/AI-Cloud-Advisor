import os
from supabase import create_client
import streamlit as st

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ORGANIZATION_COLUMN = "organization_id"


def _require_organization_id(organization_id):
    value = str(organization_id or "").strip()
    if not value:
        raise ValueError("organization_id is required for dashboard queries")
    return value

@st.cache_data(ttl=300, show_spinner=False)
def fetch_kpi_total_cloud_spend(organization_id):
    organization_id = _require_organization_id(organization_id)
    resp = (
        supabase.table("kpi_total_cloud_spend")
        .select("cloud_spend")
        .eq(ORGANIZATION_COLUMN, organization_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]["cloud_spend"]
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_kpi_spend_by_cloud(organization_id):
    organization_id = _require_organization_id(organization_id)
    resp = (
        supabase.table("kpi_spend_by_cloud")
        .select("cloud,spend")
        .eq(ORGANIZATION_COLUMN, organization_id)
        .order("date", desc=True)
        .limit(10)
        .execute()
    )
    return resp.data or []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_mart_cost_anomalies(organization_id):
    organization_id = _require_organization_id(organization_id)
    resp = (
        supabase.table("mart_cost_anomalies")
        .select("date,account_id,service,anomaly_score,details")
        .eq(ORGANIZATION_COLUMN, organization_id)
        .order("date", desc=True)
        .limit(10)
        .execute()
    )
    return resp.data or []

