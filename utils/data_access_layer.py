def get_cost_anomalies():
    return []

def get_inactive_saas_users():
    return []

def get_governance_changes_timeline():
    return []

def log_workspace_activity(*args, **kwargs):
    pass
def get_total_cloud_spend(org_id):
    """Returns total cloud spend for the org."""
    try:
        # Example: Replace with actual Supabase query
        data = {"total_cloud_spend": 125000, "total_clouds": 3, "total_accounts": 5, "total_services": 12}
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e), "data": {"total_cloud_spend": 0, "total_clouds": 0, "total_accounts": 0, "total_services": 0}}

def get_cost_breakdown(org_id):
    """Returns cost breakdown by service/cloud for the org."""
    try:
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def get_finops_savings(org_id):
    """Returns realized/potential FinOps savings for the org."""
    try:
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

# Approvals
def get_pending_approvals(org_id):
    """Returns recommendations pending approval for the org."""
    try:
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def approve_recommendation(recommendation_id, approver):
    """Approve a recommendation."""
    try:
        # Example: Replace with actual Supabase update
        return {"success": True, "data": True}
    except Exception as e:
        return {"success": False, "error": str(e), "data": False}

# Operations
def get_active_incidents(org_id):
    """Returns a list of active incidents for the org."""
    try:
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def get_cost_anomalies(org_id):
    """Returns cost anomalies for the org."""
    try:
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

# SaaS
def get_inactive_saas_users(org_id):
    """Returns inactive SaaS users for the org."""
    try:
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

# Audit
def get_governance_changes_timeline(org_id):
    """Returns governance changes timeline for the org."""
    try:
        return {"success": True, "data": []}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def get_active_alerts(org_id):
    return 14

def get_open_recommendations(org_id):
    return 32

def get_savings_opportunity(org_id):
    return 28000

def get_saas_license_utilization(org_id):
    return []

def get_approvals_assignments_timeline(org_id):
    return []
# --- Audit Timeline Placeholder ---
def get_approvals_assignments_timeline(org_id):
    return [
        {
            "timestamp": "2026-05-18",
            "event": "Budget Approval",
            "user": "ceo@company.com"
        }
    ]
# --- SaaS License Utilization Placeholder ---
def get_saas_license_utilization(org_id):
    return [
        {
            "application": "Microsoft 365",
            "licenses": 500,
            "used": 420,
            "unused": 80
        },
        {
            "application": "Slack",
            "licenses": 200,
            "used": 150,
            "unused": 50
        }
    ]
# --- Temporary UI Stabilizers ---
def get_total_cloud_spend(org_id):
    return 125000

def get_active_alerts(org_id):
    return 14

def get_open_recommendations(org_id):
    return 32

def get_savings_opportunity(org_id):
    return 28000
# --- Approval Center Placeholders ---
def get_workflow_transitions(org_id=None):
    return []
def get_pending_approvals(org_id=None, tenant_id=None, **kwargs):
    """Returns recommendations pending approval for the org/tenant."""
    query = _supabase.table("recommendations").select("id,status,type,created_at,owner,impact").eq("status", "pending_approval")
    if org_id:
        query = query.eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("created_at", desc=True).limit(20).execute()
    return resp.data or []

def get_audit_logs(org_id=None):
    return []
def get_workflow_transitions(org_id=None, tenant_id=None, **kwargs):
    """Returns workflow transitions for the org/tenant."""
    query = _supabase.table("recommendation_transition_log").select("recommendation_id,from_status,to_status,changed_by,changed_at")
    if org_id:
        query = query.eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("changed_at", desc=True).limit(30).execute()
    return resp.data or []

def get_pending_approvals(org_id=None):
    return []
def get_audit_logs(org_id=None, tenant_id=None, **kwargs):
    """Returns audit logs for the org/tenant."""
    query = _supabase.table("workspace_activity_log").select("user_email,role,workspace,action,created_at")
    if org_id:
        query = query.eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("created_at", desc=True).limit(50).execute()
    return resp.data or []
# --- Semantic Recommendations Functions ---
def get_open_recommendations(org_id, tenant_id=None, **kwargs):
    """Returns open recommendations for the org/tenant."""
    query = _supabase.table("recommendations").select("id,status,type,created_at,owner,impact").eq("organization_id", org_id).eq("status", "open")
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("created_at", desc=True).limit(20).execute()
    return resp.data or []

def get_approval_queue(org_id, tenant_id=None, **kwargs):
    """Returns recommendations pending approval for the org/tenant."""
    query = _supabase.table("recommendations").select("id,status,type,created_at,owner,impact").eq("organization_id", org_id).eq("status", "pending_approval")
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("created_at", desc=True).limit(20).execute()
    return resp.data or []

# --- Semantic Governance Functions ---
def get_governance_score(org_id, tenant_id=None, **kwargs):
    """Returns governance score for the org/tenant."""
    query = _supabase.table("governance_score_history").select("date,score").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("date", desc=True).limit(1).execute()
    if resp.data:
        return resp.data[0]["score"]
    return None

def get_governance_trends(org_id, tenant_id=None, **kwargs):
    """Returns governance score trends for the org/tenant."""
    query = _supabase.table("governance_score_history").select("date,score").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("date", desc=True).limit(30).execute()
    return resp.data or []

# --- Semantic Observability Functions ---
def get_etl_health(org_id, tenant_id=None, **kwargs):
    """Returns ETL job health for the org/tenant."""
    query = _supabase.table("etl_job_runs").select("job_name,status,started_at,completed_at,duration_seconds,records_processed,error_message").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("started_at", desc=True).limit(20).execute()
    return resp.data or []

def get_mart_health(org_id, tenant_id=None, **kwargs):
    """Returns mart refresh health for the org/tenant."""
    query = _supabase.table("mart_refresh_history").select("mart_name,refresh_started_at,refresh_completed_at,status,row_count,refresh_duration_seconds").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("refresh_started_at", desc=True).limit(20).execute()
    return resp.data or []

def get_ai_health(org_id, tenant_id=None, **kwargs):
    """Returns AI model health for the org/tenant."""
    query = _supabase.table("ai_model_registry").select("model_name,model_version,model_type,status,trained_at,inference_last_run,training_window,accuracy_score").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("trained_at", desc=True).limit(10).execute()
    return resp.data or []

# --- Semantic Audit Functions ---
def get_recent_activity(org_id, tenant_id=None, **kwargs):
    """Returns recent workspace activity for the org/tenant."""
    query = _supabase.table("workspace_activity_log").select("user_email,role,workspace,action,created_at").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("created_at", desc=True).limit(30).execute()
    return resp.data or []

def get_recent_transitions(org_id, tenant_id=None, **kwargs):
    """Returns recent workflow transitions for the org/tenant."""
    query = _supabase.table("recommendation_transition_log").select("recommendation_id,from_status,to_status,changed_by,changed_at").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("changed_at", desc=True).limit(30).execute()
    return resp.data or []
# --- Operations Workspace ---
def get_active_incidents(org_id):
    """Returns a list of active incidents for the org."""
    # TODO: Implement actual data retrieval
    return []
# =====================
# Semantic Data Access Layer
# =====================

# --- Spend ---
# Alerting Health: compute alert metrics from alert_history
def get_alerting_health(org_id, window_hours=24):
    """
    Returns alerting health metrics: alerts_last_24h, failed_alerts, unresolved_alerts, avg_resolution_time.
    """
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)

# --- Anomalies ---
    since = (now - timedelta(hours=window_hours)).isoformat()
    # Fetch all alerts in window
    resp = (
        _supabase.table("alert_history")
        .select("status,created_at,resolved_at")
        .eq("organization_id", org_id)
        .gte("created_at", since)
        .limit(1000)
        .execute()

# --- Recommendations ---
    )
    alerts = resp.data or []
    alerts_last_24h = len(alerts)
    failed_alerts = sum(1 for a in alerts if a.get("status", "").lower() == "failed")
    unresolved_alerts = sum(1 for a in alerts if a.get("status", "").lower() not in {"resolved", "closed"})
    # Compute avg resolution time (in minutes)
    res_times = []
    for a in alerts:
        created = a.get("created_at")

# --- Governance ---
        resolved = a.get("resolved_at")
        try:
            if created and resolved:
                c_dt = datetime.fromisoformat(created)
                r_dt = datetime.fromisoformat(resolved)
                res_times.append((r_dt - c_dt).total_seconds() / 60.0)
        except Exception:
            pass
    avg_resolution_time = sum(res_times) / len(res_times) if res_times else None

# --- Observability ---
    return {
        "alerts_last_24h": alerts_last_24h,
        "failed_alerts": failed_alerts,
        "unresolved_alerts": unresolved_alerts,
        "avg_resolution_time": avg_resolution_time,
    }
# Ingestion Freshness: compute freshness_minutes for each provider
from datetime import datetime, timezone

def get_ingestion_freshness(org_id, providers=("AWS", "Azure", "GCP", "SaaS")):
    """
    Returns a dict of provider -> freshness_minutes, based on MAX(usage_date) and MAX(ingested_at) in workspace_health_status.
    """
    results = {}

# --- Audit ---
    now = datetime.now(timezone.utc)
    for provider in providers:
        resp = (
            _supabase.table("workspace_health_status")
            .select("metric_details")
            .eq("organization_id", org_id)
            .eq("metric_name", "ingestion_freshness")
            .eq("component", provider)
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            details = resp.data[0].get("metric_details", {})
            usage_date = details.get("usage_date")
            ingested_at = details.get("ingested_at")
            try:
                usage_dt = datetime.fromisoformat(usage_date) if usage_date else None
                ingested_dt = datetime.fromisoformat(ingested_at) if ingested_at else None
                if usage_dt and ingested_dt:
                    freshness = (ingested_dt - usage_dt).total_seconds() / 60.0
                elif usage_dt:
                    freshness = (now - usage_dt).total_seconds() / 60.0
                else:
                    freshness = None
            except Exception:
                freshness = None
            results[provider] = freshness
        else:
            results[provider] = None
    return results
# AI Model Freshness: fetch latest model info for a given org/model
def get_ai_model_freshness(org_id, model_name=None, status=None):
    """
    Returns latest model info (training date, health, inference freshness) for a given org/model.
    """
    query = (
        _supabase.table("ai_model_registry")
        .select("*")
        .eq("organization_id", org_id)
        .order("trained_at", desc=True)
    )
    if model_name:
        query = query.eq("model_name", model_name)
    if status:
        query = query.eq("status", status)
    resp = query.limit(5).execute()
    return resp.data or []
# Mart Refresh Health: fetch latest refresh status for a mart
from datetime import datetime, timedelta

def get_mart_refresh_health(org_id, mart_name=None, window_hours=24, status=None):
    """
    Returns latest refresh status, row count, and duration for a mart in the last window_hours.
    """
    since = (datetime.utcnow() - timedelta(hours=window_hours)).isoformat()
    query = (
        _supabase.table("mart_refresh_history")
        .select("*")
        .eq("organization_id", org_id)
        .gte("refresh_started_at", since)
        .order("refresh_started_at", desc=True)
    )
    if mart_name:
        query = query.eq("mart_name", mart_name)
    if status:
        query = query.eq("status", status)
    resp = query.limit(10).execute()
    return resp.data or []
# ETL Latency KPIs: AVG/MAX duration_seconds for a job over a time window
from datetime import datetime, timedelta

def get_etl_latency_kpis(org_id, job_name, window_hours=24, status='success'):
    """
    Returns AVG and MAX duration_seconds for a given ETL job in the last window_hours.
    """
    since = (datetime.utcnow() - timedelta(hours=window_hours)).isoformat()
    query = (
        _supabase.table("etl_job_runs")
        .select("duration_seconds")
        .eq("organization_id", org_id)
        .eq("job_name", job_name)
        .gte("started_at", since)
    )
    if status:
        query = query.eq("status", status)
    resp = query.execute()
    durations = [float(row["duration_seconds"]) for row in (resp.data or []) if row["duration_seconds"] is not None]
    if not durations:
        return {"avg": None, "max": None, "count": 0}
    return {
        "avg": sum(durations) / len(durations),
        "max": max(durations),
        "count": len(durations),
    }
# Workspace Health Status: fetch latest health metrics for a workspace
def get_workspace_health_status(org_id, tenant_id=None, account_id=None, metric_name=None):
    query = _supabase.table("workspace_health_status").select("*").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    if account_id:
        query = query.eq("account_id", account_id)
    if metric_name:
        query = query.eq("metric_name", metric_name)
    resp = query.order("recorded_at", desc=True).limit(20).execute()
    return resp.data or []
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
_supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Data Access Layer ---


# --- Semantic Spend Functions ---
def get_total_cloud_spend(org_id, tenant_id=None, **kwargs):
    """Returns total cloud spend for the org/tenant."""
    query = _supabase.table("kpi_total_cloud_spend").select("cloud_spend").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("date", desc=True).limit(1).execute()
    if resp.data:
        return resp.data[0]["cloud_spend"]
    return None

def get_spend_by_cloud(org_id, tenant_id=None, **kwargs):
    """Returns spend by cloud provider for the org/tenant."""
    query = _supabase.table("kpi_spend_by_cloud").select("cloud,spend,date").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("date", desc=True).limit(10).execute()
    return resp.data or []

def get_top_services(org_id, tenant_id=None, **kwargs):
    """Returns top cloud services by spend for the org/tenant."""
    query = _supabase.table("kpi_top_services").select("service,spend,cloud,date").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("date", desc=True).limit(10).execute()
    return resp.data or []

# --- Semantic Anomalies Functions ---
def get_active_anomalies(org_id, tenant_id=None, **kwargs):
    """Returns currently active cost anomalies for the org/tenant."""
    query = _supabase.table("mart_cost_anomalies").select("date,account_id,service,anomaly_score,details").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    query = query.gte("date", since)
    resp = query.order("date", desc=True).limit(20).execute()
    return resp.data or []

def get_anomaly_trends(org_id, tenant_id=None, **kwargs):
    """Returns anomaly trends over time for the org/tenant."""
    query = _supabase.table("mart_cost_anomalies").select("date,anomaly_score").eq("organization_id", org_id)
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    resp = query.order("date", desc=True).limit(30).execute()
    return resp.data or []

def get_optimization_opportunities(organization_id):
    resp = _supabase.table("mart_optimization_opportunities").select("date,account_id,type,impact,status,details").eq("organization_id", organization_id).order("date", desc=True).limit(10).execute()
    return resp.data or []

def get_governance_score_history(organization_id):
    resp = _supabase.table("governance_score_history").select("date,score").eq("organization_id", organization_id).order("date", desc=True).limit(30).execute()
    return resp.data or []

def get_recommendations(organization_id):
    resp = _supabase.table("recommendations").select("id,status,type,created_at,owner,impact").eq("organization_id", organization_id).order("created_at", desc=True).limit(10).execute()
    return resp.data or []

