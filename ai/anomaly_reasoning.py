import json
import os
from typing import Any, Iterable, Mapping

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


def _fallback_anomaly_reasoning(anomalies: Iterable[Mapping[str, Any]]) -> str:
    rows = list(anomalies or [])
    if not rows:
        return "No anomaly records provided."

    high = [a for a in rows if str(a.get("severity", "")).lower() in {"high", "critical"}]
    largest = max(rows, key=lambda a: float(a.get("impact", 0) or 0))

    return (
        "Anomaly Reasoning\\n"
        f"- Total anomalies reviewed: {len(rows)}\\n"
        f"- High/Critical anomalies: {len(high)}\\n"
        f"- Largest impact anomaly: {largest.get('id', 'unknown')} ({largest.get('impact', 0)})\\n"
        "- Likely causes: workload spikes, configuration drift, or coverage gaps in commitments.\\n"
        "- Next step: validate usage pattern and owner, then apply targeted remediation."
    )


def _build_prompt(anomalies: Iterable[Mapping[str, Any]], context: Mapping[str, Any] | None) -> str:
    payload = {
        "anomalies": list(anomalies or []),
        "context": dict(context or {}),
    }
    return (
        "Reason over the anomalies and explain likely causes, impact, confidence, and next actions. "
        "Group similar anomalies and prioritize by financial risk.\\n\\n"
        f"Input: {json.dumps(payload, default=str)}"
    )


def generate_anomaly_reasoning(
    anomalies: Iterable[Mapping[str, Any]],
    context: Mapping[str, Any] | None = None,
) -> str:
    """
    Explain why anomalies happened and what to do next.
    Uses OpenAI when available, otherwise deterministic fallback logic.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return _fallback_anomaly_reasoning(anomalies)

    prompt = _build_prompt(anomalies, context)

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a cloud anomaly investigator focused on finance and governance outcomes.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or _fallback_anomaly_reasoning(anomalies)
    except Exception:
        return _fallback_anomaly_reasoning(anomalies)

