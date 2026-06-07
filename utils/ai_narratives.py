def generate_executive_summary(
    governance_score=0,
    total_spend=0,
    anomaly_count=0,
    savings=0,
):
    """
    Generate executive-level cloud summary.
    """

    if governance_score >= 85:
        governance_status = "strong"
    elif governance_score >= 70:
        governance_status = "stable"
    else:
        governance_status = "at risk"

    if anomaly_count >= 15:
        anomaly_risk = "elevated operational anomalies"
    elif anomaly_count >= 5:
        anomaly_risk = "moderate anomaly activity"
    else:
        anomaly_risk = "minimal operational anomalies"

    if savings >= 1000:
        optimization_state = "significant optimization opportunities"
    elif savings > 0:
        optimization_state = "moderate optimization potential"
    else:
        optimization_state = "limited immediate optimization gains"

    return f"""
AI Cloud Advisor has analyzed your multi-cloud operating posture.

Current governance maturity is assessed as {governance_status} with a governance score of {governance_score}/100.

Total observed cloud spend is ${total_spend:,.2f}, with {anomaly_risk} detected across monitored environments.

The optimization engine identified {optimization_state}, with an estimated ${savings:,.2f} in actionable savings opportunities.

Executive recommendation:
Continue governance standardization while prioritizing anomaly remediation and optimization workflow adoption to improve operational efficiency.
"""


def generate_risk_narrative(risk_level="MODERATE"):
    """
    Generate executive risk narrative.
    """

    mapping = {
        "LOW": "Operational risk exposure remains controlled with minimal governance drift detected.",
        "MODERATE": "Some operational inconsistencies and idle resource patterns require governance review.",
        "HIGH": "Multiple unmanaged resources and anomaly patterns indicate elevated operational and financial risk exposure.",
    }

    return mapping.get(
        risk_level,
        "Risk posture currently under evaluation."
    )


def generate_forecast_narrative(projected_spend=0, trend="Stable", variance=0, wow_change_pct=None, top_driver=None):
    """
    Generate executive forecast narrative with dynamic WoW language and driver attribution.

    Parameters
    ----------
    projected_spend : float
        Projected monthly spend from the forecast model.
    trend : str
        Trend classification: Stable | Moderate Growth | High Growth.
    variance : float
        Forecast variance percentage.
    wow_change_pct : float or None
        Week-over-week spend change percentage. Positive = growth, negative = reduction.
    top_driver : str or None
        Top cost driver label (e.g. "Azure compute workloads"). Used in narrative attribution.
    """

    if not (projected_spend and projected_spend > 0):
        return (
            "Forecast intelligence is currently building baseline models from ingested billing "
            "and operational telemetry. Forecast confidence improves automatically as additional "
            "historical cloud utilization data becomes available."
        )

    # ── WoW language ────────────────────────────────────────────────────────
    if wow_change_pct is not None:
        direction = "upward" if wow_change_pct >= 0 else "downward"
        wow_abs = abs(wow_change_pct)
        driver_clause = f" driven primarily by {top_driver}" if top_driver else ""
        wow_sentence = (
            f"Cloud spend is trending {direction} by {wow_abs:.1f}% week-over-week"
            f"{driver_clause}."
        )
    else:
        wow_sentence = ""

    # ── Trend-specific insight ───────────────────────────────────────────────
    if trend == "Stable":
        trend_insight = (
            "Forecast stability indicates governance controls are effectively containing "
            "cloud growth. No executive intervention required at this time."
        )
    elif trend == "Moderate Growth":
        trend_insight = (
            "Moderate growth trajectory detected. Proactive optimisation review is recommended "
            "to prevent budget overrun before month-end close."
        )
    else:  # High Growth
        trend_insight = (
            "High growth trajectory signals potential budget breach. Immediate executive review "
            "of cost drivers and governance controls is advised."
        )

    # ── Variance commentary ──────────────────────────────────────────────────
    if variance >= 15:
        variance_note = f"Elevated forecast variance of {variance:.1f}% indicates significant spend volatility — anomaly review recommended."
    elif variance >= 5:
        variance_note = f"Forecast variance of {variance:.1f}% reflects moderate spend volatility within acceptable governance thresholds."
    else:
        variance_note = f"Low forecast variance of {variance:.1f}% confirms stable and predictable cloud spend behaviour."

    parts = [
        f"Forecast models project a monthly cloud spend trajectory of ${projected_spend:,.2f}.",
        wow_sentence,
        trend_insight,
        variance_note,
        "Continued optimisation execution may reduce projected monthly spend exposure.",
    ]
    return " ".join(p for p in parts if p)

