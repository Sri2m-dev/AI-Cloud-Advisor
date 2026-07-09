"""In-memory identity resolver for P3 canonical entities."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy

from data_fabric.contracts import EnterpriseEntity
from data_fabric.identity.exceptions import IdentityValidationError
from data_fabric.identity.interfaces import IdentityResolver
from data_fabric.identity.matching import (
    MatchCandidate,
    MatchDecision,
    MatchResult,
    score_match,
)


class InMemoryIdentityResolver(IdentityResolver):
    """Deterministic, non-persistent identity resolver for canonical entities."""

    def __init__(self, entities: Iterable[EnterpriseEntity] | None = None) -> None:
        self._entities: list[EnterpriseEntity] = []
        if entities is not None:
            self.register_entities(entities)

    def register_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        self._validate_entity(entity)
        stored = self._copy_entity(entity)
        self._entities.append(stored)
        return self._copy_entity(stored)

    def register_entities(
        self,
        entities: Iterable[EnterpriseEntity],
    ) -> list[EnterpriseEntity]:
        return [self.register_entity(entity) for entity in entities]

    def resolve(self, candidate: MatchCandidate) -> MatchResult:
        self._validate_candidate(candidate)
        matches = self._rank_matches(candidate)
        if not matches:
            return MatchResult(
                decision=MatchDecision.NO_MATCH,
                candidate=candidate,
                confidence_score=0.0,
                match_reason="no_match",
            )

        top_score = matches[0][0]
        top_reason = matches[0][1]
        top_matches = [match for match in matches if match[0] == top_score]
        if len(top_matches) > 1:
            return MatchResult(
                decision=MatchDecision.DUPLICATE,
                candidate=candidate,
                confidence_score=top_score,
                match_reason=top_reason,
                matched_entities=tuple(self._copy_entity(item[2]) for item in top_matches),
            )

        matched_entity = self._copy_entity(matches[0][2])
        return MatchResult(
            decision=MatchDecision.MATCH,
            candidate=candidate,
            confidence_score=top_score,
            match_reason=top_reason,
            matched_entity=matched_entity,
            matched_entities=(matched_entity,),
        )

    def detect_duplicates(self, candidate: MatchCandidate) -> MatchResult:
        self._validate_candidate(candidate)
        matches = self._rank_matches(candidate)
        duplicate_matches = [match for match in matches if match[0] >= 0.8]
        if len(duplicate_matches) < 2:
            return self.resolve(candidate)
        best_score = duplicate_matches[0][0]
        best_reason = duplicate_matches[0][1]
        return MatchResult(
            decision=MatchDecision.DUPLICATE,
            candidate=candidate,
            confidence_score=best_score,
            match_reason=best_reason,
            matched_entities=tuple(
                self._copy_entity(match[2]) for match in duplicate_matches
            ),
        )

    def _rank_matches(
        self,
        candidate: MatchCandidate,
    ) -> list[tuple[float, str, EnterpriseEntity]]:
        matches = []
        for entity in self._entities:
            score, reason = score_match(candidate, entity)
            if score > 0:
                matches.append((score, reason, entity))
        return sorted(matches, key=lambda item: (-item[0], item[2].canonical_id))

    @staticmethod
    def _validate_candidate(candidate: MatchCandidate) -> None:
        required = {
            "source_system": candidate.source_system,
            "source_identifier": candidate.source_identifier,
            "name": candidate.name,
            "organization_id": candidate.organization_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise IdentityValidationError(
                f"Match candidate is missing required field(s): {', '.join(missing)}"
            )

    @staticmethod
    def _validate_entity(entity: EnterpriseEntity) -> None:
        required = {
            "id": entity.id,
            "canonical_id": entity.canonical_id,
            "source_system": entity.source_system,
            "source_identifier": entity.source_identifier,
            "name": entity.name,
            "organization_id": entity.organization_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise IdentityValidationError(
                f"Entity is missing required field(s): {', '.join(missing)}"
            )

    @staticmethod
    def _copy_entity(entity: EnterpriseEntity) -> EnterpriseEntity:
        return deepcopy(entity)
