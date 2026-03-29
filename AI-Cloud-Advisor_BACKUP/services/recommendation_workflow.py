from database.db import save_recommendation


def seed_ai_advisor_recommendations(username):
    recommendations = [
        {
            "category": "compute",
            "title": "Downsize underutilized EC2 instances",
            "description": "Several EC2 instances show sustained low CPU and memory utilization and can move to smaller instance classes.",
            "resource": "aws-prod:EC2",
            "estimated_savings": 840,
            "priority": "high",
            "confidence_score": 0.91,
            "rationale": "The workload profile is steady enough that sustained under-utilization is unlikely to be a short-lived demand trough.",
            "effort_level": "medium",
            "action_steps": [
                "Review the last 14 days of CPU and memory utilization by instance family.",
                "Select one smaller target size per workload and validate reservation or Savings Plan coverage.",
                "Schedule a controlled resize during the next maintenance window and confirm performance after cutover.",
            ],
        },
        {
            "category": "commitments",
            "title": "Evaluate Savings Plans coverage gaps",
            "description": "Current on-demand usage patterns indicate a Savings Plans opportunity across stable workloads.",
            "resource": "aws-shared:SavingsPlans",
            "estimated_savings": 1260,
            "priority": "high",
            "confidence_score": 0.87,
            "rationale": "The spend pattern is broad-based and persistent, which makes commitment planning more defensible than a one-off anomaly response.",
            "effort_level": "medium",
            "action_steps": [
                "Measure the recurring hourly spend that remained on-demand for the past month.",
                "Compare one-year and three-year Savings Plans scenarios against expected workload volatility.",
                "Create a commitment proposal with break-even assumptions and review it with engineering owners.",
            ],
        },
        {
            "category": "storage",
            "title": "Archive stale snapshots and cold backups",
            "description": "Backup retention appears higher than required for several low-access datasets.",
            "resource": "shared:backups",
            "estimated_savings": 430,
            "priority": "medium",
            "confidence_score": 0.78,
            "rationale": "Snapshot age and low recovery demand suggest the current retention window is wider than the likely recovery requirement.",
            "effort_level": "low",
            "action_steps": [
                "Identify snapshots older than the policy baseline and group them by application owner.",
                "Confirm legal and recovery retention requirements before deleting or archiving copies.",
                "Apply lifecycle rules so the cleanup does not need to be repeated manually.",
            ],
        },
    ]

    for item in recommendations:
        save_recommendation(
            username=username,
            category=item["category"],
            title=item["title"],
            description=item["description"],
            source="ai_advisor",
            resource=item["resource"],
            estimated_savings=item["estimated_savings"],
            priority=item["priority"],
            confidence_score=item["confidence_score"],
            rationale=item["rationale"],
            effort_level=item["effort_level"],
            action_steps=item["action_steps"],
        )

    return recommendations