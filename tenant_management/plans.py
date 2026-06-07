PLANS = {
    "Starter": {
        "features": ["Dashboards"],
        "price": 0
    },
    "Professional": {
        "features": ["Dashboards", "Governance"],
        "price": 99
    },
    "Enterprise": {
        "features": ["Dashboards", "Governance", "AI", "Automation"],
        "price": 499
    },
    "MSP": {
        "features": ["Dashboards", "Governance", "AI", "Automation", "Multi-tenant"],
        "price": 999
    }
}

def get_plan_features(plan: str):
    return PLANS.get(plan, {}).get("features", [])

