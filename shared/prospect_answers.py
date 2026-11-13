from __future__ import annotations

import re
from typing import Any

from shared.currency import format_currency_amount


def _known_context(analysis: Any, scope_label: str) -> str:
    spend = (
        "currency unresolved"
        if getattr(analysis, "currency_resolution_required", True)
        else format_currency_amount(analysis.total_spend, analysis.currency)
    )
    return (
        f"{scope_label} contains {spend} of total observed spend across "
        f"{analysis.row_count:,} records with {analysis.evidence_coverage:.1f}% evidence coverage."
    )


def _requested_subject(question: str) -> str | None:
    match = re.search(r"\b(?:of|for)\s+([a-z0-9][a-z0-9 ._/-]{0,60})\??$", question)
    if not match:
        return None
    subject = match.group(1).strip(" .?/")
    return subject.upper() if len(subject) <= 5 else subject.title()


def prospect_evidence_answer(
    question: str,
    analysis: Any,
    *,
    scope_label: str | None = None,
) -> str:
    """Answer only questions supported by the aggregate prospect analysis contract."""
    normalized = " ".join(str(question or "").lower().split())
    display_scope = "the current prospect analysis" if scope_label is None else scope_label.lower()
    unsupported_domains = (
        "risk",
        "service",
        "application",
        "decision",
        "owner",
        "dependency",
        "health",
        "realized",
        "forecast",
    )
    if any(term in normalized for term in unsupported_domains):
        if scope_label is None:
            return (
                "UNKNOWN — the current uploaded prospect evidence does not support this "
                "conclusion. Nexora will not use tenant or synthetic demonstration evidence."
            )
        return (
            f"UNKNOWN — {scope_label} evidence does not support this conclusion. "
            "Nexora will not use tenant or synthetic demonstration evidence."
        )
    if "row" in normalized or "record" in normalized:
        return (
            f"The current prospect analysis contains {analysis.row_count:,} evidence rows."
            if scope_label is None
            else f"{scope_label} contains {analysis.row_count:,} evidence rows."
        )
    if "coverage" in normalized:
        return (
            f"Current prospect evidence coverage is {analysis.evidence_coverage:.1f}%."
            if scope_label is None
            else f"{scope_label} evidence coverage is {analysis.evidence_coverage:.1f}%."
        )
    if "currency" in normalized:
        if getattr(analysis, "currency_resolution_required", True):
            if scope_label is None:
                return "UNKNOWN — currency has not been resolved for the current prospect evidence."
            return f"UNKNOWN — currency has not been resolved for {scope_label.lower()} evidence."
        if scope_label is None:
            return (
                "The governed currency for the current prospect analysis is "
                f"{analysis.currency}."
            )
        return f"The governed currency for {scope_label.lower()} is {analysis.currency}."
    if "opportunity" in normalized and any(
        term in normalized for term in ("qualified", "total", "overall", "current")
    ):
        if getattr(analysis, "currency_resolution_required", True):
            if scope_label is None:
                return "UNKNOWN — currency must be resolved before monetary analysis is finalized."
            return f"UNKNOWN — currency must be resolved before {scope_label.lower()} is finalized."
        return (
            "Evidence-qualified opportunity is "
            f"{format_currency_amount(analysis.opportunity_evidence_qualified, analysis.currency)}."
        )
    monetary_question = "spend" in normalized or "cost" in normalized
    aggregate_scope = any(
        term in normalized for term in ("total", "overall", "all spend", "entire upload")
    )
    subject = _requested_subject(normalized) if monetary_question else None
    if monetary_question and aggregate_scope and subject is None:
        if getattr(analysis, "currency_resolution_required", True):
            return "UNKNOWN — currency must be resolved before monetary analysis is finalized."
        if scope_label is None:
            return (
                "Total observed spend in the current prospect analysis is "
                f"{format_currency_amount(analysis.total_spend, analysis.currency)}."
            )
        return (
            f"Total observed spend in {display_scope} is "
            f"{format_currency_amount(analysis.total_spend, analysis.currency)}."
        )
    if monetary_question:
        specificity = f"{subject}-specific" if subject else "The requested category-specific"
        context = (
            _known_context(analysis, "The current upload")
            if scope_label is None
            else _known_context(analysis, scope_label)
        )
        return (
            f"{specificity} spend is not evidenced by {display_scope}. "
            f"{context} The normalized analysis does not provide sufficient "
            "governed classification to attribute that amount."
        )
    if scope_label is None:
        return (
            "UNKNOWN — the current uploaded prospect evidence does not support this question. "
            "Nexora will not infer an answer or use tenant or synthetic demonstration evidence."
        )
    return (
        f"UNKNOWN — {scope_label} evidence does not support this question. "
        "Nexora will not infer an answer or use tenant or synthetic demonstration evidence."
    )
