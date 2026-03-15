from copy import deepcopy
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


DEMO_SCENARIOS = {
    "healthy": {
        "label": "Healthy environment",
        "description": "Stable spend, strong cloud hygiene, and only a small number of follow-up actions.",
    },
    "cost_spike": {
        "label": "Cost spike / anomaly",
        "description": "Recent spend acceleration in compute and data services to exercise anomaly and forecast review flows.",
    },
    "waste_heavy": {
        "label": "Waste-heavy environment",
        "description": "Oversized compute and storage-heavy patterns to test optimization and savings workflows.",
    },
    "governance_failure": {
        "label": "Governance failure",
        "description": "Tagging, policy, and billing-export issues across providers to test operational remediation flows.",
    },
    "mixed_failures": {
        "label": "Mixed failures",
        "description": "Balanced demo with one healthy account, one governance issue, and one billing failure for end-to-end testing.",
    },
}


def list_demo_scenarios():
    return [{"key": key, **value} for key, value in DEMO_SCENARIOS.items()]


def _normalize_demo_scenario(scenario):
    return scenario if scenario in DEMO_SCENARIOS else "mixed_failures"


def _next_sync_at(hours=24):
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat(timespec="seconds")


def _build_cost_frame(
    service_costs,
    days=60,
    trend_factor_per_day=0.0025,
    weekly_swing=0.018,
    anomaly_days=None,
    anomaly_multiplier=1.22,
    anomaly_services=None,
    recent_spike_days=0,
    recent_spike_multiplier=1.0,
    recent_spike_services=None,
):
    start_date = datetime.utcnow().date() - timedelta(days=days - 1)
    anomaly_day_set = set(anomaly_days or [])
    anomaly_service_set = set(anomaly_services or [])
    recent_spike_service_set = set(recent_spike_services or [])
    rows = []
    for day_index in range(days):
        current_date = start_date + timedelta(days=day_index)
        trend_factor = 1 + (day_index * trend_factor_per_day)
        weekly_factor = 1 + (((day_index % 7) - 3) * weekly_swing)
        for service_name, base_cost in service_costs.items():
            service_factor = 1 + ((len(service_name) % 5) * 0.015)
            anomaly_factor = 1.0
            if anomaly_day_set and current_date.day in anomaly_day_set and service_name in anomaly_service_set:
                anomaly_factor *= anomaly_multiplier
            if recent_spike_days and day_index >= max(days - recent_spike_days, 0) and service_name in recent_spike_service_set:
                anomaly_factor *= recent_spike_multiplier
            cost_value = round(base_cost * trend_factor * weekly_factor * service_factor * anomaly_factor, 2)
            rows.append(
                {
                    "date": current_date.isoformat(),
                    "Service": service_name,
                    "Cost": max(cost_value, 0.0),
                }
            )
    return pd.DataFrame(rows)


def _base_demo_accounts():
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
            "cost_pattern": {
                "anomaly_days": [7, 21],
                "anomaly_multiplier": 1.22,
                "anomaly_services": ["EC2"],
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
            "cost_pattern": {
                "anomaly_days": [7, 21],
                "anomaly_multiplier": 1.18,
                "anomaly_services": ["Virtual Machines"],
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
            "cost_pattern": {
                "anomaly_days": [7, 21],
                "anomaly_multiplier": 1.2,
                "anomaly_services": ["BigQuery"],
            },
        },
    ]


def _demo_accounts(scenario="mixed_failures"):
    scenario = _normalize_demo_scenario(scenario)
    accounts = deepcopy(_base_demo_accounts())

    if scenario == "healthy":
        healthy_profiles = {
            "aws": {
                "details": {"status": "validated", "message": "Demo AWS account is healthy and syncing on schedule.", "health_score": 98, "sync_frequency_hours": 24},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"EC2": 109.0, "RDS": 63.0, "S3": 24.0, "Data Transfer": 12.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": []},
            },
            "azure": {
                "details": {"status": "validated", "message": "Demo Azure subscription is healthy with consistent spend.", "health_score": 95, "sync_frequency_hours": 12},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"Virtual Machines": 101.0, "Storage": 30.0, "SQL Database": 58.0, "Bandwidth": 10.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": []},
            },
            "gcp": {
                "details": {"status": "validated", "message": "Demo GCP billing export is healthy and current.", "health_score": 94, "sync_frequency_hours": 24},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"BigQuery": 64.0, "Cloud Storage": 22.0, "Compute Engine": 79.0, "Cloud Functions": 11.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": []},
            },
        }
    elif scenario == "cost_spike":
        healthy_profiles = {
            "aws": {
                "details": {"status": "validated", "message": "AWS spend has accelerated sharply in the last 10 days.", "health_score": 81, "sync_frequency_hours": 6},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"EC2": 138.0, "RDS": 76.0, "S3": 31.0, "Data Transfer": 23.0},
                "cost_pattern": {"recent_spike_days": 10, "recent_spike_multiplier": 1.68, "recent_spike_services": ["EC2", "Data Transfer"], "anomaly_days": [7, 21], "anomaly_multiplier": 1.18, "anomaly_services": ["EC2"]},
            },
            "azure": {
                "details": {"status": "validated", "message": "Azure analytics workloads show an ongoing cost spike.", "health_score": 79, "sync_frequency_hours": 6},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"Virtual Machines": 124.0, "Storage": 35.0, "SQL Database": 71.0, "Bandwidth": 18.0},
                "cost_pattern": {"recent_spike_days": 12, "recent_spike_multiplier": 1.44, "recent_spike_services": ["Virtual Machines", "Bandwidth"], "anomaly_days": [7, 21], "anomaly_multiplier": 1.15, "anomaly_services": ["Virtual Machines"]},
            },
            "gcp": {
                "details": {"status": "validated", "message": "GCP query demand increased materially near month-end.", "health_score": 84, "sync_frequency_hours": 12},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"BigQuery": 97.0, "Cloud Storage": 25.0, "Compute Engine": 103.0, "Cloud Functions": 14.0},
                "cost_pattern": {"recent_spike_days": 9, "recent_spike_multiplier": 1.36, "recent_spike_services": ["BigQuery", "Compute Engine"], "anomaly_days": [7, 21], "anomaly_multiplier": 1.16, "anomaly_services": ["BigQuery"]},
            },
        }
    elif scenario == "waste_heavy":
        healthy_profiles = {
            "aws": {
                "details": {"status": "validated", "message": "AWS has oversized compute and idle capacity in the demo estate.", "health_score": 72, "sync_frequency_hours": 24},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"EC2": 182.0, "RDS": 96.0, "S3": 48.0, "Data Transfer": 18.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": [], "trend_factor_per_day": 0.0015},
            },
            "azure": {
                "details": {"status": "validated", "message": "Azure contains underused VM reservations and unattached storage.", "health_score": 69, "sync_frequency_hours": 24},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"Virtual Machines": 161.0, "Storage": 58.0, "SQL Database": 77.0, "Bandwidth": 12.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": [], "trend_factor_per_day": 0.0012},
            },
            "gcp": {
                "details": {"status": "validated", "message": "GCP project mix shows stale datasets and always-on compute in demo.", "health_score": 74, "sync_frequency_hours": 24},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"BigQuery": 91.0, "Cloud Storage": 44.0, "Compute Engine": 126.0, "Cloud Functions": 11.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": [], "trend_factor_per_day": 0.0018},
            },
        }
    elif scenario == "governance_failure":
        healthy_profiles = {
            "aws": {
                "details": {"status": "warning", "message": "AWS resources are syncing, but critical tags are missing across shared services.", "health_score": 58, "sync_frequency_hours": 24},
                "sync_status": "synced",
                "sync_run_status": "success",
                "last_error": None,
                "service_costs": {"EC2": 129.0, "RDS": 75.0, "S3": 29.0, "Data Transfer": 17.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": []},
            },
            "azure": {
                "details": {"status": "error", "message": "Azure policy assignment failed and budgets are not enforced in the demo subscription.", "health_score": 43, "sync_frequency_hours": 12},
                "sync_status": "error",
                "sync_run_status": "failed",
                "last_error": "Cost Management access is blocked by a missing reader assignment.",
                "service_costs": {"Virtual Machines": 118.0, "Storage": 34.0, "SQL Database": 66.0, "Bandwidth": 11.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": []},
            },
            "gcp": {
                "details": {"status": "error", "message": "GCP billing export is stale and project labels are incomplete in the demo environment.", "health_score": 38, "sync_frequency_hours": 24},
                "sync_status": "error",
                "sync_run_status": "failed",
                "last_error": "Billing export table is stale and missing cost-center labels.",
                "service_costs": {"BigQuery": 83.0, "Cloud Storage": 24.0, "Compute Engine": 96.0, "Cloud Functions": 13.0},
                "cost_pattern": {"anomaly_days": [], "anomaly_services": []},
            },
        }
    else:
        healthy_profiles = {}

    for account in accounts:
        overrides = healthy_profiles.get(account["provider"])
        if overrides:
            account.update(overrides)
    return accounts


def get_demo_account_profiles(scenario="mixed_failures"):
    return deepcopy(_demo_accounts(scenario))


def _demo_recommendation_resources():
    return {
        "aws-prod-finops:EC2",
        "aws-prod-finops:idle-compute",
        "aws-prod-finops:untagged-services",
        "azure-finance-subscription:tags",
        "azure-finance-subscription:policy",
        "azure-finance-subscription:vm-waste",
        "gcp-analytics-billing:billing-export",
        "gcp-analytics-billing:query-spike",
        "gcp-analytics-billing:idle-datasets",
        "shared:untagged-spend",
        "shared:idle-resources",
        "shared:forecast-variance",
        "shared:forecast-spike",
        "shared:cost-spike-anomaly",
        "shared:storage-waste",
        "shared:governance-gap",
        "aws-shared:SavingsPlans",
        "shared:backups",
    }


def _demo_recommendation_details(item, scenario):
    category = str(item.get("category") or "").lower()
    priority = str(item.get("priority") or "medium").lower()
    title = item.get("title") or "this recommendation"
    provider = (item.get("provider") or "shared").upper()

    confidence_score = {
        "high": 0.9,
        "medium": 0.78,
        "low": 0.66,
    }.get(priority, 0.72)

    effort_level = {
        "governance": "medium",
        "policy": "high",
        "billing-export": "high",
        "anomaly": "medium",
        "forecast": "low",
        "rightsizing": "medium",
        "storage": "low",
        "commitments": "medium",
        "query-optimization": "medium",
    }.get(category, "medium")

    rationale = (
        f"This {scenario.replace('_', ' ')} demo scenario was seeded to make {title.lower()} a visible operational follow-up "
        f"for the {provider} estate."
    )

    default_steps = [
        "Confirm the affected account scope and validate the issue against the seeded demo signals.",
        "Assign an owner and capture the remediation decision in the workflow notes or activity history.",
        "Re-check the dashboard after remediation to verify the scenario impact moved in the expected direction.",
    ]
    category_steps = {
        "anomaly": [
            "Compare the last two weeks of spend against the prior baseline to isolate the spike window.",
            "Review the top services and accounts contributing to the variance.",
            "Decide whether the increase is expected demand or avoidable waste before month-end actions are taken.",
        ],
        "forecast": [
            "Validate whether the forecast jump is driven by a recent spike or a broader trend shift.",
            "Check if commitments, reservations, or scheduling changes could offset the projected increase.",
            "Document the decision so the finance review has a clear explanation for the variance.",
        ],
        "rightsizing": [
            "Review utilization and instance-sizing evidence for the affected workloads.",
            "Select the lowest-risk resize candidates and confirm owner approval.",
            "Implement the change in a maintenance window and monitor post-change performance.",
        ],
        "storage": [
            "Identify cold or duplicated data that no longer matches recent access patterns.",
            "Choose archive, lifecycle, or deletion actions for each storage tier.",
            "Apply policy changes so the waste pattern does not recur in the demo workflow.",
        ],
        "governance": [
            "List the missing tags, owners, or budget controls affecting cost accountability.",
            "Apply the minimum policy or tagging remediation needed to restore showback quality.",
            "Re-run validation and confirm the governance gap disappears from the scenario view.",
        ],
        "policy": [
            "Restore the missing access assignment or policy binding blocking cost controls.",
            "Validate budget and reader coverage across the affected subscription or project.",
            "Capture the fix in the workflow so the operations team can audit the remediation.",
        ],
        "billing-export": [
            "Repair the export pipeline or dataset permissions causing incomplete billing data.",
            "Backfill the missing usage window and confirm labels needed for showback are present.",
            "Re-run sync validation and verify the account health score improves.",
        ],
        "commitments": [
            "Quantify recurring baseline demand before proposing new commitments.",
            "Model savings against likely usage volatility and ownership horizon.",
            "Prepare a commitment recommendation with explicit break-even assumptions.",
        ],
        "query-optimization": [
            "Inspect the largest query or analytics jobs driving the month-end surge.",
            "Target partitioning, caching, or scheduling changes that reduce repeated scans.",
            "Track the cost delta after the change to confirm the optimization impact.",
        ],
    }

    return {
        "confidence_score": item.get("confidence_score", confidence_score),
        "rationale": item.get("rationale") or rationale,
        "effort_level": item.get("effort_level") or effort_level,
        "action_steps": item.get("action_steps") or category_steps.get(category, default_steps),
    }


def _seed_demo_recommendations(username, accounts, scenario="mixed_failures"):
    scenario = _normalize_demo_scenario(scenario)
    account_lookup = {account["provider"]: account for account in accounts}
    available_providers = set(account_lookup)
    scenario_recommendations = {
        "healthy": [
            {
                "category": "governance",
                "title": "Review minor untagged spend drift",
                "description": "A small amount of shared spend is untagged in the otherwise healthy demo environment.",
                "source": "demo_environment",
                "resource": "shared:untagged-spend",
                "account_identifier": None,
                "provider": None,
                "owner": username,
                "priority": "low",
                "estimated_savings": 240,
                "due_date": (datetime.utcnow().date() + timedelta(days=10)).isoformat(),
            }
        ],
        "cost_spike": [
            {
                "category": "anomaly",
                "title": "Investigate compute cost spike",
                "description": "AWS and Azure compute costs accelerated sharply in the last ten days of the demo period.",
                "source": "demo_environment",
                "resource": "shared:cost-spike-anomaly",
                "account_identifier": account_lookup.get("aws", {}).get("account_identifier"),
                "provider": "aws",
                "owner": username,
                "priority": "high",
                "estimated_savings": 3100,
                "due_date": (datetime.utcnow().date() + timedelta(days=2)).isoformat(),
            },
            {
                "category": "forecast",
                "title": "Validate forecast increase drivers",
                "description": "Recent cost acceleration is large enough to change the next-month forecast materially.",
                "source": "demo_environment",
                "resource": "shared:forecast-variance",
                "account_identifier": None,
                "provider": None,
                "owner": username,
                "priority": "high",
                "estimated_savings": 1800,
                "due_date": (datetime.utcnow().date() + timedelta(days=3)).isoformat(),
            },
            {
                "category": "query-optimization",
                "title": "Review BigQuery demand surge",
                "description": "The demo GCP account shows a sustained increase in analytics query volume near month-end.",
                "source": "demo_environment",
                "resource": "gcp-analytics-billing:query-spike",
                "account_identifier": account_lookup.get("gcp", {}).get("account_identifier"),
                "provider": "gcp",
                "owner": username,
                "priority": "medium",
                "estimated_savings": 950,
                "due_date": (datetime.utcnow().date() + timedelta(days=4)).isoformat(),
            },
            {
                "category": "forecast",
                "title": "Investigate 1-month forecast spike",
                "description": "The seeded forecast projects a material increase versus the recent baseline so the workflow and dashboard risk summary can be tested.",
                "source": "cost_forecast",
                "resource": "shared:forecast-spike",
                "account_identifier": None,
                "provider": None,
                "owner": username,
                "priority": "high",
                "estimated_savings": 3600,
                "due_date": (datetime.utcnow().date() + timedelta(days=3)).isoformat(),
            },
        ],
        "waste_heavy": [
            {
                "category": "rightsizing",
                "title": "Rightsize idle compute fleet",
                "description": "The demo environment contains oversized compute with persistent low utilization across providers.",
                "source": "demo_environment",
                "resource": "aws-prod-finops:idle-compute",
                "account_identifier": account_lookup.get("aws", {}).get("account_identifier"),
                "provider": "aws",
                "owner": username,
                "priority": "high",
                "estimated_savings": 4700,
                "due_date": (datetime.utcnow().date() + timedelta(days=5)).isoformat(),
            },
            {
                "category": "storage",
                "title": "Reduce cold storage waste",
                "description": "Azure and GCP storage tiers are oversized relative to recent access patterns in the demo estate.",
                "source": "demo_environment",
                "resource": "shared:storage-waste",
                "account_identifier": None,
                "provider": None,
                "owner": username,
                "priority": "high",
                "estimated_savings": 2300,
                "due_date": (datetime.utcnow().date() + timedelta(days=6)).isoformat(),
            },
            {
                "category": "commitments",
                "title": "Review underused reserved capacity",
                "description": "The demo Azure subscription simulates low utilization against reserved compute commitments.",
                "source": "demo_environment",
                "resource": "azure-finance-subscription:vm-waste",
                "account_identifier": account_lookup.get("azure", {}).get("account_identifier"),
                "provider": "azure",
                "owner": None,
                "priority": "medium",
                "estimated_savings": 1400,
                "due_date": (datetime.utcnow().date() + timedelta(days=7)).isoformat(),
            },
        ],
        "governance_failure": [
            {
                "category": "governance",
                "title": "Remediate missing ownership tags",
                "description": "AWS shared services in the demo environment are missing application and cost-center tags.",
                "source": "demo_environment",
                "resource": "aws-prod-finops:untagged-services",
                "account_identifier": account_lookup.get("aws", {}).get("account_identifier"),
                "provider": "aws",
                "owner": None,
                "priority": "high",
                "estimated_savings": 1200,
                "due_date": (datetime.utcnow().date() + timedelta(days=2)).isoformat(),
            },
            {
                "category": "policy",
                "title": "Restore Azure cost policy coverage",
                "description": "The demo Azure subscription is missing a working reader assignment and budget policy enforcement.",
                "source": "demo_environment",
                "resource": "azure-finance-subscription:policy",
                "account_identifier": account_lookup.get("azure", {}).get("account_identifier"),
                "provider": "azure",
                "owner": username,
                "priority": "high",
                "estimated_savings": 0,
                "due_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
            },
            {
                "category": "billing-export",
                "title": "Repair stale GCP billing export",
                "description": "The demo GCP export is stale and missing key governance labels needed for showback.",
                "source": "demo_environment",
                "resource": "gcp-analytics-billing:billing-export",
                "account_identifier": account_lookup.get("gcp", {}).get("account_identifier"),
                "provider": "gcp",
                "owner": username,
                "priority": "high",
                "estimated_savings": 1500,
                "due_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
            },
            {
                "category": "governance",
                "title": "Close shared governance gap",
                "description": "Cross-provider governance controls are incomplete in the demo environment and need remediation.",
                "source": "demo_environment",
                "resource": "shared:governance-gap",
                "account_identifier": None,
                "provider": None,
                "owner": None,
                "priority": "medium",
                "estimated_savings": 600,
                "due_date": (datetime.utcnow().date() + timedelta(days=4)).isoformat(),
            },
        ],
        "mixed_failures": [
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
            {
                "category": "forecast",
                "title": "Investigate 1-month forecast spike",
                "description": "The mixed-failures demo includes a seeded forecast risk so Dashboard and Recommendations can be tested without opening Cost Forecast first.",
                "source": "cost_forecast",
                "resource": "shared:forecast-spike",
                "account_identifier": None,
                "provider": None,
                "owner": username,
                "priority": "medium",
                "estimated_savings": 1800,
                "due_date": (datetime.utcnow().date() + timedelta(days=4)).isoformat(),
            },
        ],
    }
    recommendations = [
        item
        for item in scenario_recommendations[scenario]
        if item.get("provider") is None or item.get("provider") in available_providers
    ]

    recommendation_ids = []
    for item in recommendations:
        recommendation_payload = {**item, **_demo_recommendation_details(item, scenario)}
        recommendation_ids.append(
            save_recommendation(
                username=username,
                category=recommendation_payload["category"],
                title=recommendation_payload["title"],
                description=recommendation_payload["description"],
                source=recommendation_payload["source"],
                resource=recommendation_payload["resource"],
                account_identifier=recommendation_payload["account_identifier"],
                provider=recommendation_payload["provider"],
                owner=recommendation_payload["owner"],
                priority=recommendation_payload["priority"],
                estimated_savings=recommendation_payload["estimated_savings"],
                due_date=recommendation_payload["due_date"],
                confidence_score=recommendation_payload["confidence_score"],
                rationale=recommendation_payload["rationale"],
                effort_level=recommendation_payload["effort_level"],
                action_steps=recommendation_payload["action_steps"],
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


def seed_demo_environment(username, max_accounts=3, scenario="mixed_failures"):
    scenario = _normalize_demo_scenario(scenario)
    reset_demo_environment(username)
    selected_accounts = _demo_accounts(scenario)[: max(1, int(max_accounts or 1))]
    total_billing_rows = 0

    for account in selected_accounts:
        cost_pattern = account.get("cost_pattern", {})
        cost_frame = _build_cost_frame(account["service_costs"], **cost_pattern)
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

    recommendation_count = _seed_demo_recommendations(username, selected_accounts, scenario=scenario)
    log_audit_event(
        username,
        "demo_environment_seeded",
        f"scenario={scenario}, accounts={len(selected_accounts)}, billing_rows={total_billing_rows}, recommendations={recommendation_count}",
    )
    return {
        "scenario": scenario,
        "accounts": len(selected_accounts),
        "account_names": [account["account_name"] for account in selected_accounts],
        "providers": [account["provider"] for account in selected_accounts],
        "billing_rows": total_billing_rows,
        "recommendations": recommendation_count,
    }


def reset_demo_environment(username):
    conn = get_db()
    demo_accounts = _demo_accounts()
    demo_identifiers = [account["account_identifier"] for account in demo_accounts]
    demo_account_names = [account["account_name"] for account in demo_accounts]
    demo_resources = list(_demo_recommendation_resources())
    identifier_placeholders = ", ".join("?" for _ in demo_identifiers)
    resource_placeholders = ", ".join("?" for _ in demo_resources)

    cloud_account_rows = conn.execute(
        f"""
        SELECT id
        FROM cloud_accounts
        WHERE username = ? AND account_identifier IN ({identifier_placeholders})
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

    recommendation_sources = ("demo_environment", "dashboard", "ai_advisor", "cost_forecast")
    recommendation_count = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM recommendations
        WHERE username = ?
          AND (
              source IN (?, ?, ?, ?)
              OR account_identifier IN ({identifier_placeholders})
              OR resource IN ({resource_placeholders})
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
        f"""
        DELETE FROM recommendation_events
        WHERE recommendation_id IN (
            SELECT id
            FROM recommendations
            WHERE username = ?
              AND (
                  source IN (?, ?, ?, ?)
                  OR account_identifier IN ({identifier_placeholders})
                  OR resource IN ({resource_placeholders})
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
        f"""
        DELETE FROM recommendations
        WHERE username = ?
          AND (
              source IN (?, ?, ?, ?)
              OR account_identifier IN ({identifier_placeholders})
              OR resource IN ({resource_placeholders})
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
        f"SELECT COUNT(*) FROM cloud_accounts WHERE username = ? AND account_identifier IN ({identifier_placeholders})",
        (username, *demo_identifiers),
    ).fetchone()[0]
    conn.execute(
        f"DELETE FROM cloud_accounts WHERE username = ? AND account_identifier IN ({identifier_placeholders})",
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