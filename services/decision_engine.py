def generate_decision(best_option, roi, suitability, risk, complexity):
    provider = best_option["provider"]
    decision = {
        "target_cloud": provider,
        "savings": best_option["savings"],
        "performance": best_option["performance_gain"],
        "payback": roi,
        "suitability": suitability,
        "risk": risk,
        "complexity": complexity,
    }

    if "High" in risk:
        decision["recommendation"] = f"🚫 Recommendation: Do NOT migrate to {provider}"
        decision["final"] = "🔴 Not Recommended"
        decision["reason"] = "High migration risk outweighs cost savings"
        decision["approach"] = "Mitigate dependencies and simplify architecture first"
        decision["savings_note"] = f"💰 Potential Savings: ${decision['savings']} (if risk mitigated)"
    elif "Medium" in risk:
        decision["recommendation"] = f"⚠️ Recommendation: Move to {provider} (Phased Migration)"
        decision["final"] = "🟡 Recommended with phased migration"
        decision["reason"] = "Moderate migration risk can be managed through staged execution"
        decision["approach"] = "Gradual workload shift"
        decision["savings_note"] = f"💰 Potential Savings: ${decision['savings']}"
    else:
        decision["recommendation"] = f"✅ Recommendation: Move to {provider}"
        decision["final"] = "✅ Strongly Recommended"
        decision["reason"] = "Low migration risk supports a direct move"
        decision["approach"] = "Standard migration rollout"
        decision["savings_note"] = f"💰 Potential Savings: ${decision['savings']}"

    return decision
