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
def fetch_kpi_top_services(organization_id):
    organization_id = _require_organization_id(organization_id)
    resp = (
        supabase.table("kpi_top_services")
        .select("service,spend,cloud,date")
        .eq(ORGANIZATION_COLUMN, organization_id)
        .order("date", desc=True)
        .limit(10)
        .execute()
    )
    return resp.data or []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_mart_optimization_opportunities(organization_id):
    organization_id = _require_organization_id(organization_id)
    resp = (
        supabase.table("mart_optimization_opportunities")
        .select("date,account_id,type,impact,status,details")
        .eq(ORGANIZATION_COLUMN, organization_id)
        .order("date", desc=True)
        .limit(10)
        .execute()
    )
    return resp.data or []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_governance_score_history(organization_id):
    organization_id = _require_organization_id(organization_id)
    resp = (
        supabase.table("governance_score_history")
        .select("date,score")
        .eq(ORGANIZATION_COLUMN, organization_id)
        .order("date", desc=True)
        .limit(30)
        .execute()
    )
    return resp.data or []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_recommendations(organization_id):
    organization_id = _require_organization_id(organization_id)
    resp = (
        supabase.table("recommendations")
        .select("id,status,type,created_at,owner,impact")
        .eq(ORGANIZATION_COLUMN, organization_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return resp.data or []

