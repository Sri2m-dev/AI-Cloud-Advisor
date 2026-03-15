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
        },
        {
            "category": "commitments",
            "title": "Evaluate Savings Plans coverage gaps",
            "description": "Current on-demand usage patterns indicate a Savings Plans opportunity across stable workloads.",
            "resource": "aws-shared:SavingsPlans",
            "estimated_savings": 1260,
            "priority": "high",
        },
        {
            "category": "storage",
            "title": "Archive stale snapshots and cold backups",
            "description": "Backup retention appears higher than required for several low-access datasets.",
            "resource": "shared:backups",
            "estimated_savings": 430,
            "priority": "medium",
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
        )

    return recommendations