from __future__ import annotations


def get_azure_optimization_recommendations() -> list[dict]:
    return [
        {
            "category": "rightsizing",
            "title": "Rightsize underutilized Azure VM fleet",
            "description": "Azure Advisor indicates low-utilization virtual machines that can be downsized with low performance risk.",
            "resource": "azure-prod:VirtualMachines",
            "estimated_savings": 3900,
            "priority": "high",
            "confidence_score": 0.88,
            "rationale": "Consistent low CPU and memory utilization suggests immediate rightsize opportunities on VM workloads.",
            "effort_level": "medium",
            "action_steps": [
                "Review Azure Advisor cost recommendations for target VM families.",
                "Validate CPU, memory, and disk throughput headroom for each candidate.",
                "Resize during a maintenance window and monitor latency and error budgets.",
            ],
        },
        {
            "category": "commitments",
            "title": "Increase Azure Savings Plan and Reservation coverage",
            "description": "Apply Azure Savings Plans for Compute and Reservations to steady-state workloads to reduce pay-as-you-go spend.",
            "resource": "azure-prod:Commitments",
            "estimated_savings": 4600,
            "priority": "high",
            "confidence_score": 0.86,
            "rationale": "Steady baseline consumption makes commitment-based discounts a high-confidence savings lever.",
            "effort_level": "low",
            "action_steps": [
                "Review current commitment coverage and underutilized reservation inventory.",
                "Purchase 1-year commitments for the most stable VM and database workloads.",
                "Track commitment utilization monthly and rebalance scope where needed.",
            ],
        },
        {
            "category": "idle_resources",
            "title": "Shut down idle Azure disks, IPs, and orphaned resources",
            "description": "Detect unattached managed disks, unused public IPs, and stale non-production resources to eliminate waste.",
            "resource": "azure-shared:IdleResources",
            "estimated_savings": 1400,
            "priority": "medium",
            "confidence_score": 0.92,
            "rationale": "Idle infrastructure spend is typically low-risk to reclaim when ownership and retention checks are completed.",
            "effort_level": "low",
            "action_steps": [
                "List unattached managed disks and idle public IP addresses.",
                "Snapshot or export required data for retention compliance.",
                "Delete confirmed orphaned resources and validate savings next billing cycle.",
            ],
        },
        {
            "category": "governance",
            "title": "Automate Azure budgets, exports, and tag policy enforcement",
            "description": "Use Cost Management exports, budget thresholds, and Azure Policy tagging to improve cost accountability.",
            "resource": "azure-shared:CostGovernance",
            "estimated_savings": 1100,
            "priority": "medium",
            "confidence_score": 0.81,
            "rationale": "Better visibility and accountability reduce long-tail waste and accelerate corrective action.",
            "effort_level": "low",
            "action_steps": [
                "Set monthly budgets with threshold alerts at 70%, 85%, and 100%.",
                "Enable scheduled Cost Management exports to your analytics store.",
                "Enforce mandatory tags (Environment, Team, CostCenter, Owner) via Azure Policy.",
            ],
        },
    ]

