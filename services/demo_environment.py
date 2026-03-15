from datetime import datetime, timedelta

import pandas as pd

from database.db import (
    create_sync_run,
    finish_sync_run,
    get_db,
    log_audit_event,
    record_cloud_account_sync_result,
    save_cloud_account,
    save_cost_data,
    save_recommendation,
    update_cloud_account_health,
    update_recommendation_status,
)


def _next_sync_at(hours=24):
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat(timespec="seconds")


def _build_cost_frame(service_costs, days=60):
    start_date = datetime.utcnow().date() - timedelta(days=days - 1)
    rows = []
    for day_index in range(days):
        current_date = start_date + timedelta(days=day_index)
        trend_factor = 1 + (day_index * 0.0025)
        weekly_factor = 1 + (((day_index % 7) - 3) * 0.018)
        for service_name, base_cost in service_costs.items():
            service_factor = 1 + ((len(service_name) % 5) * 0.015)
            anomaly_factor = 1.0
            if current_date.day in {7, 21} and service_name in {"EC2", "Virtual Machines", "BigQuery"}:
                anomaly_factor = 1.22
            cost_value = round(base_cost * trend_factor * weekly_factor * service_factor * anomaly_factor, 2)
            rows.append(
                {
                    "date": current_date.isoformat(),
                    "Service": service_name,
                    "Cost": max(cost_value, 0.0),
                }
            )
    return pd.DataFrame(rows)


def _demo_accounts():
    return [
        {
            "provider": "aws",
            "account_name": "aws-prod-finops",
            "account_identifier": "arn:aws:iam::123456789012:role/finops-demo-role",
            "credentials": {
                "role_arn": "arn:aws:iam::123456789012:role/finops-demo-role",
                "external_id": "demo-external-id",
            },
            "details": {
                "status": "validated",
                "message": "Demo AWS account seeded successfully.",
                "health_score": 97,
                "sync_frequency_hours": 24,
            },
            "sync_status": "synced",
            "sync_run_status": "success",
            "last_error": None,
            "service_costs": {
                "EC2": 132.0,
                "RDS": 74.0,
                "S3": 28.0,
                "Data Transfer": 16.0,
            },
        },
        {
            "provider": "azure",
            "account_name": "azure-finance-subscription",
            "account_identifier": "00000000-1111-2222-3333-444444444444",
            "credentials": {
                "tenant_id": "demo-tenant-id",
                "client_id": "demo-client-id",
                "client_secret": "demo-client-secret",
                "subscription_id": "00000000-1111-2222-3333-444444444444",
            },
            "details": {
                "status": "validated",
                "message": "Demo Azure subscription seeded successfully.",
                "health_score": 91,
                "sync_frequency_hours": 12,
            },
            "sync_status": "synced",
            "sync_run_status": "success",
            "last_error": None,
            "service_costs": {
                "Virtual Machines": 118.0,
                "Storage": 34.0,
                "SQL Database": 66.0,
                "Bandwidth": 11.0,
            },
        },
        {
            "provider": "gcp",
            "account_name": "gcp-analytics-billing",
            "account_identifier": "projects/demo-billing/datasets/cloud_billing/tables/export_v1",
            "credentials": {
                "service_account_json": "{\"type\": \"service_account\", \"project_id\": \"demo-billing\"}",
                "billing_project_id": "demo-billing",
                "billing_dataset": "cloud_billing",
                "billing_table": "export_v1",
                "billing_account_id": "0000-1111-2222",
            },
            "details": {
                "status": "error",
                "message": "Demo GCP export seeded with a validation issue for troubleshooting flows.",
                "health_score": 63,
                "sync_frequency_hours": 24,
            },
            "sync_status": "error",
            "sync_run_status": "failed",
            "last_error": "Billing export table is stale in the demo environment.",
            "service_costs": {
                "BigQuery": 82.0,
                "Cloud Storage": 24.0,
                "Compute Engine": 97.0,
                "Cloud Functions": 13.0,
            },
        },
    ]


def _demo_recommendation_resources():
    return {
        "aws-prod-finops:EC2",
        "azure-finance-subscription:tags",
        "gcp-analytics-billing:billing-export",
        "shared:untagged-spend",
        "shared:idle-resources",
        "shared:forecast-variance",
        "aws-shared:SavingsPlans",
        "shared:backups",
    }


def _seed_demo_recommendations(username, accounts):
    account_lookup = {account["provider"]: account for account in accounts}
    recommendations = [
        {
            "category": "rightsizing",
            "title": "Rightsize EC2 compute cluster",
            "description": "Several EC2 instances in the demo AWS account are consistently underutilized.",
            "source": "demo_environment",
            "resource": "aws-prod-finops:EC2",
            "account_identifier": account_lookup.get("aws", {}).get("account_identifier"),
            "provider": "aws",
            "owner": username,
            "priority": "high",
            "estimated_savings": 4200,
            "due_date": (datetime.utcnow().date() + timedelta(days=5)).isoformat(),
        },
        {
            "category": "governance",
            "title": "Tag unowned Azure resources",
            "description": "The demo Azure subscription contains resources missing application and cost-center tags.",
            "source": "demo_environment",
            "resource": "azure-finance-subscription:tags",
            "account_identifier": account_lookup.get("azure", {}).get("account_identifier"),
            "provider": "azure",
            "owner": None,
            "priority": "medium",
            "estimated_savings": 900,
            "due_date": (datetime.utcnow().date() - timedelta(days=2)).isoformat(),
        },
        {
            "category": "billing-export",
            "title": "Repair stale GCP billing export",
            "description": "The demo GCP account simulates a stale billing export so the failure workflow can be tested.",
            "source": "demo_environment",
            "resource": "gcp-analytics-billing:billing-export",
            "account_identifier": account_lookup.get("gcp", {}).get("account_identifier"),
            "provider": "gcp",
            "owner": username,
            "priority": "high",
            "estimated_savings": 1500,
            "due_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
        },
    ]

    recommendation_ids = []
    for item in recommendations:
        recommendation_ids.append(
            save_recommendation(
                username=username,
                category=item["category"],
                title=item["title"],
                description=item["description"],
                source=item["source"],
                resource=item["resource"],
                account_identifier=item["account_identifier"],
                provider=item["provider"],
                owner=item["owner"],
                priority=item["priority"],
                estimated_savings=item["estimated_savings"],
                due_date=item["due_date"],
            )
        )

    if recommendation_ids:
        update_recommendation_status(
            recommendation_ids[0],
            "accepted",
            username=username,
            owner=username,
            notes="Accepted automatically for demo workflow setup.",
        )
        update_recommendation_status(
            recommendation_ids[-1],
            "snoozed",
            username=username,
            notes="Snoozed automatically for demo workflow setup.",
        )
    return len(recommendations)


def seed_demo_environment(username, max_accounts=3):
    selected_accounts = _demo_accounts()[: max(1, int(max_accounts or 1))]
    total_billing_rows = 0

    for account in selected_accounts:
        cost_frame = _build_cost_frame(account["service_costs"])
        total_billing_rows += int(len(cost_frame.index))

        account_id = save_cloud_account(
            username=username,
            provider=account["provider"],
            account_name=account["account_name"],
            account_identifier=account["account_identifier"],
            credentials=account["credentials"],
            details=account["details"],
        )

        save_cost_data(account["provider"], cost_frame, account_name=account["account_name"])

        coverage_start = cost_frame["date"].min()
        coverage_end = cost_frame["date"].max()
        synced_at = datetime.utcnow().isoformat(timespec="seconds")
        next_sync_at = _next_sync_at(account["details"].get("sync_frequency_hours", 24))
        update_cloud_account_health(
            account_id,
            validation_status=account["details"].get("status"),
            validation_message=account["details"].get("message"),
            health_score=account["details"].get("health_score"),
            last_validation_at=synced_at,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            next_sync_at=next_sync_at,
            sync_frequency_hours=account["details"].get("sync_frequency_hours", 24),
        )
        record_cloud_account_sync_result(
            account_id,
            account["sync_status"],
            synced_at=synced_at if account["sync_status"] == "synced" else None,
            last_error=account["last_error"],
            duration_seconds=6.4,
            record_count=len(cost_frame.index),
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            next_sync_at=next_sync_at,
        )

        run_id = create_sync_run(
            cloud_account_id=account_id,
            username=username,
            provider=account["provider"],
            trigger_type="demo_seed",
            metadata={"account_identifier": account["account_identifier"]},
        )
        finish_sync_run(
            run_id,
            status=account["sync_run_status"],
            finished_at=synced_at,
            duration_seconds=6.4,
            record_count=len(cost_frame.index),
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            error_message=account["last_error"],
            metadata={"account_identifier": account["account_identifier"], "seeded": True},
        )

    recommendation_count = _seed_demo_recommendations(username, selected_accounts)
    log_audit_event(
        username,
        "demo_environment_seeded",
        f"accounts={len(selected_accounts)}, billing_rows={total_billing_rows}, recommendations={recommendation_count}",
    )
    return {
        "accounts": len(selected_accounts),
        "billing_rows": total_billing_rows,
        "recommendations": recommendation_count,
    }


def reset_demo_environment(username):
    conn = get_db()
    demo_accounts = _demo_accounts()
    demo_identifiers = [account["account_identifier"] for account in demo_accounts]
    demo_account_names = [account["account_name"] for account in demo_accounts]
    demo_resources = list(_demo_recommendation_resources())

    cloud_account_rows = conn.execute(
        """
        SELECT id
        FROM cloud_accounts
        WHERE username = ? AND account_identifier IN (?, ?, ?)
        """,
        (username, *demo_identifiers),
    ).fetchall()
    cloud_account_ids = [row[0] for row in cloud_account_rows]

    sync_run_count = 0
    if cloud_account_ids:
        sync_placeholders = ", ".join("?" for _ in cloud_account_ids)
        sync_run_count = conn.execute(
            f"SELECT COUNT(*) FROM cloud_sync_runs WHERE cloud_account_id IN ({sync_placeholders})",
            tuple(cloud_account_ids),
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM cloud_sync_runs WHERE cloud_account_id IN ({sync_placeholders})",
            tuple(cloud_account_ids),
        )

    billing_placeholders = ", ".join("?" for _ in demo_account_names)
    billing_row_count = conn.execute(
        f"SELECT COUNT(*) FROM billing_data WHERE account IN ({billing_placeholders})",
        tuple(demo_account_names),
    ).fetchone()[0]
    conn.execute(
        f"DELETE FROM billing_data WHERE account IN ({billing_placeholders})",
        tuple(demo_account_names),
    )

    recommendation_sources = ("demo_environment", "dashboard", "ai_advisor")
    recommendation_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM recommendations
        WHERE username = ?
          AND (
              source IN (?, ?, ?)
              OR account_identifier IN (?, ?, ?)
              OR resource IN (?, ?, ?, ?, ?, ?, ?, ?)
          )
        """,
        (
            username,
            *recommendation_sources,
            *demo_identifiers,
            *demo_resources,
        ),
    ).fetchone()[0]
    conn.execute(
        """
        DELETE FROM recommendation_events
        WHERE recommendation_id IN (
            SELECT id
            FROM recommendations
            WHERE username = ?
              AND (
                  source IN (?, ?, ?)
                  OR account_identifier IN (?, ?, ?)
                  OR resource IN (?, ?, ?, ?, ?, ?, ?, ?)
              )
        )
        """,
        (
            username,
            *recommendation_sources,
            *demo_identifiers,
            *demo_resources,
        ),
    )
    conn.execute(
        """
        DELETE FROM recommendations
        WHERE username = ?
          AND (
              source IN (?, ?, ?)
              OR account_identifier IN (?, ?, ?)
              OR resource IN (?, ?, ?, ?, ?, ?, ?, ?)
          )
        """,
        (
            username,
            *recommendation_sources,
            *demo_identifiers,
            *demo_resources,
        ),
    )

    cloud_account_count = conn.execute(
        "SELECT COUNT(*) FROM cloud_accounts WHERE username = ? AND account_identifier IN (?, ?, ?)",
        (username, *demo_identifiers),
    ).fetchone()[0]
    conn.execute(
        "DELETE FROM cloud_accounts WHERE username = ? AND account_identifier IN (?, ?, ?)",
        (username, *demo_identifiers),
    )

    conn.commit()
    conn.close()
    log_audit_event(
        username,
        "demo_environment_reset",
        f"accounts={cloud_account_count}, billing_rows={billing_row_count}, sync_runs={sync_run_count}, recommendations={recommendation_count}",
    )
    return {
        "accounts": int(cloud_account_count or 0),
        "billing_rows": int(billing_row_count or 0),
        "sync_runs": int(sync_run_count or 0),
        "recommendations": int(recommendation_count or 0),
    }