import json
import os
from typing import Any, Mapping, Sequence

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


def _safe_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fallback_executive_summary(data: Mapping[str, Any]) -> str:
    spend = _safe_number(data.get("spend"))
    savings = _safe_number(data.get("savings"))
    risks = data.get("risks") or []
    risk_count = len(risks) if isinstance(risks, Sequence) and not isinstance(risks, (str, bytes)) else 0

    savings_rate = (savings / spend * 100.0) if spend > 0 else 0.0

    return (
        "Executive Summary\\n"
        f"- Total spend: ${spend:,.2f}\\n"
        f"- Identified savings: ${savings:,.2f} ({savings_rate:.1f}% of spend)\\n"
        f"- Active risks: {risk_count}\\n"
        "- Action: Prioritize high-cost services, close critical anomalies, and track governance score weekly."
    )


def _build_prompt(data: Mapping[str, Any]) -> str:
    spend = data.get("spend", 0)
    savings = data.get("savings", 0)
    risks = data.get("risks", [])
    marts = data.get("marts", {})
    recommendations = data.get("recommendations", [])
    anomalies = data.get("anomalies", [])
    forecasts = data.get("forecasts", [])
    governance_scores = data.get("governance_scores", {})

    return f"""
Generate an executive summary for a CTO audience.
Use concise business language and include:
1) Current cloud posture
2) Savings opportunities
3) Risk posture
4) Recommended next actions (max 5)

Input:
Spend: {spend}
Savings: {savings}
Risks: {json.dumps(risks, default=str)}
Marts: {json.dumps(marts, default=str)}
Recommendations: {json.dumps(recommendations, default=str)}
Anomalies: {json.dumps(anomalies, default=str)}
Forecasts: {json.dumps(forecasts, default=str)}
Governance Scores: {json.dumps(governance_scores, default=str)}
""".strip()


def generate_cto_summary(data: Mapping[str, Any]) -> str:
    """
    Generate a CTO-level executive summary using OpenAI.
    Falls back to deterministic text if API access is unavailable.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return _fallback_executive_summary(data)

    prompt = _build_prompt(data)

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a FinOps executive advisor. Return a crisp, actionable summary.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip() or _fallback_executive_summary(data)
    except Exception:
        return _fallback_executive_summary(data)

