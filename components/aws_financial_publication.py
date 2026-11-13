"""Small canonical AWS publication panel; no financial fallback values."""

from services.aws_financial_dashboard_adapter import dashboard_status
from services.aws_financial_ingestion_composition import aws_financial_dashboard_status


def render_aws_financial_publication(context, *, ui, adapter=None, import_ids=()):
    status = (
        aws_financial_dashboard_status(context)
        if adapter is None
        else dashboard_status(context, adapter, import_ids)
    )
    ui.subheader("AWS financial publication")
    ui.caption("Source: AWS canonical financial evidence")
    ui.caption(f"Readiness: {status.readiness}")
    if status.readiness != "READY" or status.posture is None:
        ui.metric("AWS total spend", "UNKNOWN")
        ui.caption("Currency / billing period: UNKNOWN; Account / import coverage: UNKNOWN")
        ui.caption("Last verified publication: UNKNOWN")
        ui.warning(status.reason)
        return status
    posture = status.posture
    ui.metric("AWS total spend", f"{posture.cloud_spend:,.2f} {posture.currency}")
    ui.caption(f"Billing period: {posture.period_start} to {posture.period_end}")
    ui.caption(
        f"Account coverage: {posture.resolved_account_count} resolved; "
        f"import coverage: {posture.import_count}; facts: {posture.persisted_facts}"
    )
    ui.caption(f"Last verified publication: {status.published_at.isoformat()}")
    return status
