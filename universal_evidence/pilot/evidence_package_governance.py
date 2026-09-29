from __future__ import annotations

from dataclasses import dataclass

from universal_evidence.pilot.evidence_package_semantics import (
    certified_field_semantic,
)


@dataclass(frozen=True)
class CertifiedPackageGovernanceResult:
    source_type: str
    confirmed_count: int
    skipped_count: int
    decisions: tuple[object, ...]


def govern_certified_package_source(
    *,
    admission,
    source_type: str,
    semantic_service,
    actor,
) -> CertifiedPackageGovernanceResult:
    """
    Apply the certified package contract through Nexora's existing
    semantic-governance authority.

    Only exact fields in the certified package semantic profile are eligible.
    Unsupported fields remain observed/unmapped.

    No MappingDecision or EffectiveSemanticMapping is manufactured here.
    Every governed field passes through PilotSemanticGovernanceService.confirm().
    """

    discovery = semantic_service.discovery(admission)

    decisions: list[object] = []
    skipped_count = 0

    for column in discovery.columns:
        certified = certified_field_semantic(
            source_type,
            column.original_header,
        )

        if certified is None:
            skipped_count += 1
            continue

        effective = semantic_service.confirmation_service.get_effective_mapping(
            column,
            actor=actor,
        )

        if effective is not None and effective.semantic_concept_id == certified.semantic_concept_id:
            decision = next(
                item
                for item in semantic_service.confirmation_service.get_decision_history(
                    column,
                    actor=actor,
                ).decisions
                if item.decision_id == effective.decision_id
            )
        else:
            candidate_concepts = {candidate.semantic_concept_id for candidate in column.candidates}

            confirmation_required = False

            if certified.semantic_concept_id in candidate_concepts:
                requirement = (
                    semantic_service.confirmation_service.evaluate_confirmation_requirement(column)
                )
                confirmation_required = (
                    getattr(
                        getattr(requirement, "state", None),
                        "value",
                        getattr(requirement, "state", None),
                    )
                    == "REQUIRED"
                )

            if confirmation_required:
                decision = semantic_service.confirm(
                    admission,
                    column.source_column_reference,
                    certified.semantic_concept_id,
                    actor=actor,
                )
            else:
                decision = semantic_service.override(
                    admission,
                    column.source_column_reference,
                    certified.semantic_concept_id,
                    actor=actor,
                    reason=(
                        "Certified evidence package contract: "
                        f"{source_type}.{column.original_header}"
                    ),
                )

        decisions.append(decision)

    return CertifiedPackageGovernanceResult(
        source_type=source_type,
        confirmed_count=len(decisions),
        skipped_count=skipped_count,
        decisions=tuple(decisions),
    )
