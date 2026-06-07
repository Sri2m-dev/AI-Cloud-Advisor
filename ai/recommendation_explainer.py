import json
import os
from typing import Any, Mapping

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


def _fallback_recommendation_explanation(recommendation: Mapping[str, Any]) -> str:
    service = recommendation.get("service", "Unknown service")
    cloud = recommendation.get("cloud", "Unknown cloud")
    savings = recommendation.get("savings_monthly", recommendation.get("estimated_savings", 0))
    priority = recommendation.get("priority", "medium")

    return (
        "Recommendation Explanation\\n"
        f"- Target: {service} on {cloud}\\n"
        f"- Priority: {priority}\\n"
        f"- Estimated monthly savings: {savings}\\n"
        "- Why this matters: This action addresses a major cost driver and reduces waste without reducing business value.\\n"
        "- Suggested rollout: test in non-production, validate savings, then scale."
    )


def _build_prompt(
    recommendation: Mapping[str, Any],
    audience: str,
    context: Mapping[str, Any] | None,
) -> str:
    payload = {
        "recommendation": dict(recommendation or {}),
        "audience": audience,
        "context": dict(context or {}),
    }
    return (
        "Explain this cloud recommendation in plain language for the requested audience. "
        "Include rationale, expected impact, risk, effort, and implementation guidance.\\n\\n"
        f"Input: {json.dumps(payload, default=str)}"
    )


def explain_recommendation(
    recommendation: Mapping[str, Any],
    audience: str = "executive",
    context: Mapping[str, Any] | None = None,
) -> str:
    """
    Produce a narrative explanation for a recommendation card.
    Uses OpenAI when available, otherwise deterministic fallback text.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return _fallback_recommendation_explanation(recommendation)

    prompt = _build_prompt(recommendation, audience, context)

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a cloud governance assistant that writes clear, action-oriented explanations.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or _fallback_recommendation_explanation(recommendation)
    except Exception:
        return _fallback_recommendation_explanation(recommendation)

