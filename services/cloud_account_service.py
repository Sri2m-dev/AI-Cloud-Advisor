from datetime import date, datetime, timedelta

import pandas as pd

from database.db import (
    create_sync_run,
    decrypt_credentials,
    finish_sync_run,
    get_cloud_account,
    log_audit_event,
    record_cloud_account_sync_result,
    save_cloud_account,
    save_cost_data,
    update_cloud_account_health,
    update_cloud_account_sync_status,
)
from services.aws_connector import assume_role, get_cost_explorer_client
from services.azure_connector import get_azure_cost
from services.gcp_connector import get_gcp_cost


class CloudAccountSyncError(Exception):
    pass


def _frame_coverage_window(frame):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None, None

    if "date" in frame.columns:
        date_series = frame["date"]
    elif "Date" in frame.columns:
        date_series = frame["Date"]
    else:
        return None, None

    parsed_dates = pd.to_datetime(date_series, errors="coerce").dropna()
    if parsed_dates.empty:
        return None, None
    return parsed_dates.min().date().isoformat(), parsed_dates.max().date().isoformat()


def _validation_details(frame, extra_details=None):
    record_count = int(len(frame.index)) if isinstance(frame, pd.DataFrame) else 0
    coverage_start, coverage_end = _frame_coverage_window(frame)
    if record_count:
        message = "Connected successfully. Automatic sync is ready."
        health_score = 100
    else:
        message = "Connected successfully, but no recent billing records were returned."
        health_score = 85

    details = {
        "status": "validated",
        "message": message,
        "health_score": health_score,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "record_count": record_count,
    }
    details.update(extra_details or {})
    return details


def _next_sync_at(sync_frequency_hours):
    hours = int(sync_frequency_hours or 24)
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat(timespec="seconds")


def _aws_cost_dataframe(credentials):
    temp_creds = assume_role(credentials["role_arn"], credentials["external_id"])
    if not temp_creds:
        raise CloudAccountSyncError("Failed to assume the AWS role with the supplied Role ARN and External ID.")

    client = get_cost_explorer_client(temp_creds)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    response = client.get_cost_and_usage(
        TimePeriod={
            "Start": start_date.isoformat(),
            "End": end_date.isoformat(),
        },
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    rows = []
    for period in response.get("ResultsByTime", []):
        period_start = period["TimePeriod"]["Start"]
        for group in period.get("Groups", []):
            service_name = group.get("Keys", ["Other"])[0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            rows.append({
                "date": period_start,
                "Service": service_name,
                "Cost": amount,
            })
    return pd.DataFrame(rows)


def _azure_cost_dataframe(credentials):
    return get_azure_cost(
        credentials["tenant_id"],
        credentials["client_id"],
        credentials["client_secret"],
        credentials["subscription_id"],
    )


def _gcp_cost_dataframe(credentials):
    billing_project_id = credentials.get("billing_project_id")
    billing_dataset = credentials.get("billing_dataset")
    billing_table = credentials.get("billing_table")
    if not billing_project_id or not billing_dataset or not billing_table:
        raise CloudAccountSyncError(
            "GCP cost sync requires a billing export project, dataset, and table."
        )

    return get_gcp_cost(
        service_account_json=credentials["service_account_json"],
        billing_project_id=billing_project_id,
        billing_dataset=billing_dataset,
        billing_table=billing_table,
        billing_account_id=credentials.get("billing_account_id"),
    )


def validate_cloud_account(provider, credentials):
    provider = provider.lower()
    if provider == "aws":
        frame = _aws_cost_dataframe(credentials)
        return {
            "preview": frame.head(10).to_dict("records"),
            "cost_df": frame,
            "details": _validation_details(frame),
        }
    if provider == "azure":
        frame = _azure_cost_dataframe(credentials)
        return {
            "preview": frame.head(10).to_dict("records"),
            "cost_df": frame,
            "details": _validation_details(frame, {"subscription_id": credentials["subscription_id"]}),
        }
    if provider == "gcp":
        frame = _gcp_cost_dataframe(credentials)
        return {
            "preview": frame.head(10).to_dict("records"),
            "cost_df": frame,
            "details": _validation_details(
                frame,
                {
                    "billing_project_id": credentials["billing_project_id"],
                    "billing_dataset": credentials["billing_dataset"],
                    "billing_table": credentials["billing_table"],
                    "billing_account_id": credentials.get("billing_account_id"),
                },
            ),
        }
    raise CloudAccountSyncError(f"Unsupported provider: {provider}")


def create_cloud_account(username, provider, account_name, account_identifier, credentials):
    validation = validate_cloud_account(provider, credentials)
    account_id = save_cloud_account(
        username=username,
        provider=provider.lower(),
        account_name=account_name,
        account_identifier=account_identifier,
        credentials=credentials,
        details=validation["details"],
    )
    update_cloud_account_health(
        account_id,
        validation_status=validation["details"].get("status"),
        validation_message=validation["details"].get("message"),
        health_score=validation["details"].get("health_score"),
        last_validation_at=datetime.utcnow().isoformat(timespec="seconds"),
        coverage_start=validation["details"].get("coverage_start"),
        coverage_end=validation["details"].get("coverage_end"),
        next_sync_at=_next_sync_at(validation["details"].get("sync_frequency_hours", 24)),
        sync_frequency_hours=validation["details"].get("sync_frequency_hours", 24),
    )
    sync_cloud_account(account_id, preloaded_cost_df=validation["cost_df"], trigger_type="on_connect")
    log_audit_event(username, "cloud_account_saved", f"provider={provider.lower()}, account={account_identifier}")
    return {
        "account_id": account_id,
        "preview": validation["preview"],
    }


def sync_cloud_account(account_id, preloaded_cost_df=None, trigger_type="manual"):
    account = get_cloud_account(account_id)
    if not account:
        raise CloudAccountSyncError("Cloud account not found.")

    provider = account["provider"].lower()
    username = account.get("username", "guest")
    credentials = decrypt_credentials(account.get("credentials_encrypted"))
    sync_frequency_hours = int(account.get("sync_frequency_hours") or 24)
    started_at = datetime.utcnow()
    run_id = create_sync_run(
        cloud_account_id=account_id,
        username=username,
        provider=provider,
        trigger_type=trigger_type,
        metadata={"account_identifier": account.get("account_identifier")},
    )

    update_cloud_account_sync_status(account_id, "syncing", last_error=None)
    try:
        validation = None
        if preloaded_cost_df is not None:
            cost_df = preloaded_cost_df
            validation_details = _validation_details(cost_df)
        else:
            validation = validate_cloud_account(provider, credentials)
            cost_df = validation["cost_df"]
            validation_details = validation["details"]

        save_cost_data(provider, cost_df, account_name=account["account_name"])
        synced_at = datetime.utcnow().isoformat(timespec="seconds")
        duration_seconds = (datetime.utcnow() - started_at).total_seconds()
        record_count = int(len(cost_df.index)) if isinstance(cost_df, pd.DataFrame) else 0
        coverage_start = validation_details.get("coverage_start")
        coverage_end = validation_details.get("coverage_end")
        next_sync_at = _next_sync_at(sync_frequency_hours)

        update_cloud_account_health(
            account_id,
            validation_status=validation_details.get("status", "validated"),
            validation_message=validation_details.get("message"),
            health_score=validation_details.get("health_score", 100),
            last_validation_at=synced_at,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            next_sync_at=next_sync_at,
            sync_frequency_hours=sync_frequency_hours,
        )
        record_cloud_account_sync_result(
            account_id,
            "synced",
            synced_at=synced_at,
            duration_seconds=duration_seconds,
            record_count=record_count,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            next_sync_at=next_sync_at,
        )
        finish_sync_run(
            run_id,
            status="success",
            finished_at=synced_at,
            duration_seconds=duration_seconds,
            record_count=record_count,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            metadata={
                "account_identifier": account.get("account_identifier"),
                "trigger_type": trigger_type,
                "validation_status": validation_details.get("status", "validated"),
            },
        )
        log_audit_event(username, "cloud_account_synced", f"provider={provider}, account={account['account_identifier']}")
    except Exception as exc:
        failed_at = datetime.utcnow().isoformat(timespec="seconds")
        duration_seconds = (datetime.utcnow() - started_at).total_seconds()
        next_sync_at = _next_sync_at(sync_frequency_hours)
        update_cloud_account_health(
            account_id,
            validation_status="error",
            validation_message=str(exc),
            health_score=25,
            last_validation_at=failed_at,
            next_sync_at=next_sync_at,
            sync_frequency_hours=sync_frequency_hours,
        )
        record_cloud_account_sync_result(
            account_id,
            "error",
            last_error=str(exc),
            duration_seconds=duration_seconds,
            next_sync_at=next_sync_at,
        )
        finish_sync_run(
            run_id,
            status="error",
            finished_at=failed_at,
            duration_seconds=duration_seconds,
            error_message=str(exc),
            metadata={
                "account_identifier": account.get("account_identifier"),
                "trigger_type": trigger_type,
            },
        )
        raise CloudAccountSyncError(str(exc)) from exc
