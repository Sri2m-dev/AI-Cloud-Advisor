def calculate_complexity(resource):
    complexity = 0

    # Architecture type
    arch = resource.get("architecture", "simple")

    if arch == "monolith":
        complexity += 30
    elif arch == "microservices":
        complexity += 20
    else:
        complexity += 10

    # Integration points
    integrations = resource.get("integrations", 1)
    complexity += integrations * 5

    return complexity


def interpret_complexity(score):
    if score >= 50:
        return "🔴 High Complexity"
    elif score >= 25:
        return "🟡 Moderate Complexity"
    else:
        return "🟢 Low Complexity"
