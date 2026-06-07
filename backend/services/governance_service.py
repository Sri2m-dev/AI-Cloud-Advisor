import pandas as pd

from data.supabase_client import supabase
from backend.services.tenant_scope import scoped_query


def _severity_bucket(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"critical", "high"}:
        return "Critical"
    if raw in {"anomaly", "medium", "moderate"}:
        return "Anomaly"
    if raw in {"warning", "low"}:
        return "Warning"
    return "Normal"


def get_governance_summary(tenant_id: str) -> dict:
    try:
        response = scoped_query(supabase, "mart_cost_anomalies", tenant_id).execute()
        rows = response.data or []
    except Exception:
        rows = []

    if not rows:
        return {
            "tenant_id": tenant_id,
            "anomaly_count": 0,
            "severity_distribution": [],
            "top_findings": [],
        }

    df = pd.DataFrame(rows)
    severity_col = next((c for c in ["severity", "anomaly_level", "status"] if c in df.columns), None)
    impact_col = next((c for c in ["spike", "impact_value", "current_cost", "score"] if c in df.columns), None)
    service_col = next((c for c in ["service", "service_name", "resource", "resource_name"] if c in df.columns), None)

    if severity_col:
        df["severity_bucket"] = df[severity_col].apply(_severity_bucket)
    else:
        df["severity_bucket"] = "Anomaly"

    severity_distribution = (
        df.groupby("severity_bucket")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .to_dict("records")
    )

    top_findings = []
    if service_col:
        ranked = df.copy()
        ranked["severity_rank"] = ranked["severity_bucket"].map(
            {"Critical": 4, "Anomaly": 3, "Warning": 2, "Normal": 1}
        )
        if impact_col:
            ranked[impact_col] = pd.to_numeric(ranked[impact_col], errors="coerce").fillna(0)
            ranked = ranked.sort_values(["severity_rank", impact_col], ascending=[False, False])
        else:
            ranked = ranked.sort_values(["severity_rank"], ascending=[False])

        cols = [service_col, "severity_bucket"]
        if impact_col:
            cols.append(impact_col)
        top_findings = ranked[cols].head(10).to_dict("records")

    return {
        "tenant_id": tenant_id,
        "anomaly_count": len(rows),
        "severity_distribution": severity_distribution,
        "top_findings": top_findings,
    }

