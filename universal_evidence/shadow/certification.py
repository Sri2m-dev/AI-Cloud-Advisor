"""PUE-010 activation-readiness reporting without activation authority."""

from universal_evidence.shadow.models import ActivationReadiness, CertificationReport

DEFAULT_BLOCKERS = (
    "Production persistence is not certified.",
    "Semantic confirmation UX is not integrated.",
    "Multi-file fusion is unavailable.",
    "Natural-language vocabulary and analytical operations remain bounded.",
    "Entity resolution and production observability are unavailable.",
    "No production activation rollback mechanism is certified.",
)


def build_certification_report(scenario_outcomes):
    return CertificationReport(
        (
            "PUE-001",
            "PUE-002",
            "PUE-003",
            "PUE-004",
            "PUE-005/C5A",
            "PUE-006",
            "PUE-007/7A",
            "PUE-008",
            "PUE-009",
            "PUE-010",
        ),
        tuple(scenario_outcomes),
        (
            "Shadow inputs require separately authorized row values.",
            "Currency-grouped planning has no dedicated PUE-007 natural-language route.",
            "No production UI, session, database, or prospect-path integration exists.",
        ),
        DEFAULT_BLOCKERS,
        ActivationReadiness.READY_FOR_LIMITED_SHADOW,
    )
