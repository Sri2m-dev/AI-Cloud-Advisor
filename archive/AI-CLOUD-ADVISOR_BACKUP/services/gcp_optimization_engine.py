from __future__ import annotations


def get_gcp_optimization_recommendations() -> list[dict]:
    return [
        {
            "category": "rightsizing",
            "title": "Right-size Compute Engine and GKE workloads",
            "description": "Use FinOps Hub and Recommender insights to resize overprovisioned VM and GKE resources.",
            "resource": "gcp-prod:ComputeEngine/GKE",
            "estimated_savings": 3700,
            "priority": "high",
            "confidence_score": 0.87,
            "rationale": "Historical utilization from Recommender indicates persistent overprovisioning across compute tiers.",
            "effort_level": "medium",
            "action_steps": [
                "Review machine type and cluster sizing recommendations in FinOps Hub.",
                "Prioritize low-risk rightsize changes for development and internal services.",
                "Apply updates gradually and monitor SLO, latency, and capacity headroom.",
            ],
        },
        {
            "category": "commitments",
            "title": "Expand CUD coverage for steady GCP usage",
            "description": "Adopt spend-based and resource-based Committed Use Discounts where workloads are stable.",
            "resource": "gcp-prod:CUDs",
            "estimated_savings": 4300,
            "priority": "high",
            "confidence_score": 0.85,
            "rationale": "FinOps Hub CUD optimization opportunities show meaningful uncovered eligible spend.",
            "effort_level": "low",
            "action_steps": [
                "Review CUD optimization rate and eligible spend in FinOps Hub.",
                "Purchase commitments for stable baseline usage across core services.",
                "Track CUD utilization and adjust commitment mix quarterly.",
            ],
        },
        {
            "category": "idle_resources",
            "title": "Remove idle GCP resources and unattended projects",
            "description": "Address idle VM, disk, image, and unattended project recommendations surfaced by Recommender.",
            "resource": "gcp-shared:IdleResources",
            "estimated_savings": 1600,
            "priority": "medium",
            "confidence_score": 0.93,
            "rationale": "Idle-resource recommendations are strong waste signals with high savings certainty.",
            "effort_level": "low",
            "action_steps": [
                "Filter FinOps recommendations by idle-resource categories.",
                "Confirm ownership and retention requirements for each candidate resource.",
                "Delete or archive unused assets and verify billing impact.",
            ],
        },
        {
            "category": "governance",
            "title": "Improve FinOps score with budgets, labels, and exports",
            "description": "Strengthen cost governance by enabling label discipline, budget automation, and BigQuery billing export.",
            "resource": "gcp-shared:FinOpsGovernance",
            "estimated_savings": 900,
            "priority": "medium",
            "confidence_score": 0.8,
            "rationale": "Governance improvements increase allocation quality and reduce repeated avoidable spend.",
            "effort_level": "low",
            "action_steps": [
                "Set budget thresholds and programmatic notifications for billing accounts.",
                "Enforce labels for environment, team, and cost center across projects.",
                "Enable BigQuery billing export for recurring analysis and anomaly detection.",
            ],
        },
    ]

