def calculate_risk(resource):
    risk_score = 0

    # Dependency risk
    dep = resource.get("dependency", "low")
    if dep == "high":
        risk_score += 30
    elif dep == "medium":
        risk_score += 20
    else:
        risk_score += 10

    # Data size impact
    data_size = resource.get("data_size", "small")
    if data_size == "large":
        risk_score += 30
    elif data_size == "medium":
        risk_score += 20
    else:
        risk_score += 10

    # Downtime tolerance
    downtime = resource.get("downtime", "high")
    if downtime == "low":
        risk_score += 30
    elif downtime == "medium":
        risk_score += 20
    else:
        risk_score += 10

    return risk_score


def interpret_risk(score):
    if score >= 70:
        return "🔴 High Risk"
    elif score >= 40:
        return "🟡 Medium Risk"
    else:
        return "🟢 Low Risk"
