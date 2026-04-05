def calculate_suitability(resource):
    score = 0

    # 1. Utilization
    util = resource.get("utilization", 0)
    if util < 40:
        score += 25
    elif util < 70:
        score += 15
    else:
        score += 5

    # 2. Cost impact
    cost = resource.get("cost", 0)
    if cost > 1000:
        score += 25
    elif cost > 500:
        score += 15
    else:
        score += 5

    # 3. Stability (mock for now)
    score += 20

    # 4. Dependency risk (lower is better)
    dependency = resource.get("dependency", "low")
    if dependency == "low":
        score += 20
    elif dependency == "medium":
        score += 10
    else:
        score += 5

    # 5. Region / compliance
    score += 10

    return score


def interpret_score(score):
    if score >= 80:
        return "🟢 Highly Suitable for Migration"
    elif score >= 60:
        return "🟡 Moderately Suitable"
    else:
        return "🔴 Not Recommended for Migration"
