from __future__ import annotations

from itertools import combinations
from uuid import UUID

from core.entities.entity import EnterpriseEntity
from core.identity.confidence import confidence_from_signals, resolution_status_for_score
from core.identity.identity_match import (
    IdentityMatchCandidate,
    IdentityResolutionDecision,
    IdentityResolutionStatus,
    SourceIdentity,
    source_identities_for_entity,
)
from core.identity.match_rules import identity_match_signals
from repositories.entity_repository import EntityRepository
from repositories.identity_resolution_repository import IdentityResolutionRepository


class IdentityResolutionService:
    def __init__(
        self,
        entity_repository: EntityRepository | None = None,
        identity_repository: IdentityResolutionRepository | None = None,
    ):
        self.entity_repository = entity_repository or EntityRepository()
        self.identity_repository = identity_repository or IdentityResolutionRepository()

    def normalize_source_identity(self, source_identity: SourceIdentity) -> SourceIdentity:
        return SourceIdentity(
            system=source_identity.system.strip(),
            external_id=source_identity.external_id.strip(),
            external_name=source_identity.external_name.strip(),
            entity_type=source_identity.entity_type.strip(),
            attributes={str(key).strip().lower(): value for key, value in source_identity.attributes.items()},
        )

    def find_matching_candidates(
        self,
        source_identity: SourceIdentity,
        minimum_score: int = 1,
    ) -> list[IdentityMatchCandidate]:
        normalized = self.normalize_source_identity(source_identity)
        candidates = []
        for entity in self.entity_repository.get_entities(normalized.entity_type or None):
            for entity_identity in source_identities_for_entity(entity):
                if self.normalize_source_identity(entity_identity) == normalized:
                    candidates.extend(self.identity_repository.find_candidates(normalized))
                    break
        return [candidate for candidate in candidates if candidate.confidence_score >= minimum_score]

    def find_candidates(
        self,
        entity_type: str | None = None,
        minimum_score: int = 1,
        auto_merge: bool = True,
    ) -> list[IdentityMatchCandidate]:
        entities = self.entity_repository.get_entities(entity_type)
        candidates: list[IdentityMatchCandidate] = []
        for source, target in combinations(entities, 2):
            candidate = self.score_candidates(source, target)
            if candidate and candidate.confidence_score >= minimum_score:
                saved = self.identity_repository.save_candidate(candidate)
                candidates.append(saved)
                if auto_merge and saved.status == IdentityResolutionStatus.AUTO_MATCHED.value:
                    self.merge_entities(saved.source_entity_id, saved.target_entity_id, saved.id, notes="Auto-merged high-confidence identity match.")
        return sorted(candidates, key=lambda candidate: candidate.confidence_score, reverse=True)

    def score_candidates(
        self,
        source: EnterpriseEntity,
        target: EnterpriseEntity,
    ) -> IdentityMatchCandidate | None:
        if source.id == target.id or source.entity_type != target.entity_type:
            return None

        signals = identity_match_signals(source, target)
        confidence_score = confidence_from_signals(signals)
        status = resolution_status_for_score(confidence_score)
        if confidence_score <= 0:
            return None
        return IdentityMatchCandidate(
            source_entity_id=source.id,
            target_entity_id=target.id,
            source_display_name=source.display_name,
            target_display_name=target.display_name,
            entity_type=source.entity_type,
            confidence_score=confidence_score,
            status=status,
            signals=signals,
        )

    def auto_merge_high_confidence(self, entity_type: str | None = None) -> list[EnterpriseEntity]:
        merged_entities = []
        for candidate in self.find_candidates(entity_type, minimum_score=90, auto_merge=False):
            if candidate.status == IdentityResolutionStatus.AUTO_MATCHED.value:
                merged_entities.append(
                    self.merge_entities(
                        candidate.source_entity_id,
                        candidate.target_entity_id,
                        candidate.id,
                        notes="Auto-merged high-confidence identity match.",
                    )
                )
        return merged_entities

    def queue_medium_confidence(self, entity_type: str | None = None) -> list[IdentityMatchCandidate]:
        return [
            candidate
            for candidate in self.find_candidates(entity_type, minimum_score=70, auto_merge=False)
            if candidate.status == IdentityResolutionStatus.NEEDS_REVIEW.value
        ]

    def reject_low_confidence(self, entity_type: str | None = None) -> list[IdentityMatchCandidate]:
        rejected = []
        for candidate in self.find_candidates(entity_type, minimum_score=1, auto_merge=False):
            if candidate.status == IdentityResolutionStatus.REJECTED.value:
                self.identity_repository.reject_match(candidate.id, notes="Rejected low-confidence identity match.")
                rejected.append(candidate)
        return rejected

    def approve_match(
        self,
        candidate_id: UUID | str,
        decided_by: UUID | None = None,
        notes: str = "",
    ) -> EnterpriseEntity:
        candidate = self._get_candidate(candidate_id)
        self.identity_repository.approve_match(candidate.id, decided_by=decided_by, notes=notes)
        return self.merge_entities(candidate.source_entity_id, candidate.target_entity_id, candidate.id, decided_by, notes)

    def reject_match(
        self,
        candidate_id: UUID | str,
        decided_by: UUID | None = None,
        notes: str = "",
    ) -> IdentityResolutionDecision:
        return self.identity_repository.reject_match(candidate_id, decided_by=decided_by, notes=notes)

    def merge_entities(
        self,
        source_entity_id: UUID | str,
        target_entity_id: UUID | str,
        candidate_id: UUID | str | None = None,
        decided_by: UUID | None = None,
        notes: str = "",
    ) -> EnterpriseEntity:
        merged = self.entity_repository.merge(source_entity_id, target_entity_id)
        self.identity_repository.merge_entities(source_entity_id, target_entity_id)
        if candidate_id:
            self.identity_repository.record_decision(
                IdentityResolutionDecision(
                    candidate_id=UUID(str(candidate_id)),
                    status=IdentityResolutionStatus.MERGED.value,
                    source_entity_id=UUID(str(source_entity_id)),
                    target_entity_id=UUID(str(target_entity_id)),
                    decided_by=decided_by,
                    notes=notes,
                )
            )
        return merged

    def get_resolution_history(self, entity_id: UUID | str) -> list[dict]:
        return self.identity_repository.get_resolution_history(entity_id)

    def _get_candidate(self, candidate_id: UUID | str) -> IdentityMatchCandidate:
        candidate = self.identity_repository.get_candidate(candidate_id)
        if not candidate:
            raise KeyError(f"Identity match candidate not found: {candidate_id}")
        return candidate

