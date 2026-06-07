def get_mock_data():
    return [
        {"service_name": "EC2", "cost": 1200},
        {"service_name": "S3", "cost": 300},
        {"service_name": "RDS", "cost": 700}
    ]

def get_mock_data():
    return [
        {"service_name": "EC2", "cost": 1200},
        {"service_name": "S3", "cost": 300},
        {"service_name": "RDS", "cost": 700}
    ]


def get_cto_data():

    return {
        "executive_signal": {
            "cost_risk": "HIGH",
            "cost_risk_delta": "+12%",
            "optimization_potential": 12000,
            "cloud_concentration": "70% AWS",
            "efficiency_score": 80,
            "efficiency_delta": -4
        },
        "kpis": {
            "infrastructure_spend": 2200,
            "spend_change": "+18%",
            "active_services": 3,
            "cloud_coverage": 3,
            "architecture_health": 87
        },
        "service_costs": {
            "Compute": 1200,
            "Storage": 700,
            "Networking": 300
        }
    }

def get_ceo_data():
    return {
        "business_summary": {
            "monthly_cloud_spend": 2200,
            "budget_variance": "+10%",
            "optimization_opportunity": 12000,
            "risk_level": "Moderate"
        },
        "kpis": {
            "business_units": 4,
            "cost_per_unit": 550,
            "efficiency_index": 78
        },
        "trends": {
            "Jan": 1800,
            "Feb": 2000,
            "Mar": 2200
        }
    }

def get_finops_data():
    return {
        "summary": {
            "total_spend": 2200,
            "savings_identified": 12000,
            "realized_savings": 4000,
            "utilization_rate": 72
        },
        "cost_breakdown": {
            "AWS": 1500,
            "Azure": 500,
            "GCP": 200
        },
        "optimization_items": [
            {
                "service": "EC2",
                "issue": "Underutilized",
                "potential_savings": 3000
            },
            {
                "service": "S3",
                "issue": "Over-provisioned",
                "potential_savings": 2000
            }
        ]
    }

