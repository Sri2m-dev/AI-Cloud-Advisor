from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.identity.identity_match import (
    IdentityMatchCandidate,
    IdentityMatchSignal,
    IdentityResolutionDecision,
    IdentityResolutionStatus,
    SourceIdentity,
)


DEFAULT_IDENTITY_STORE = Path("data/identity_resolution.json")


class IdentityResolutionRepository:
    def __init__(self, store_path: str | Path = DEFAULT_IDENTITY_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._candidates: dict[UUID, IdentityMatchCandidate] = {}
        self._decisions: list[IdentityResolutionDecision] = []
        self._history: list[dict] = []
        self._load()

    def find_candidates(self, source_identity: SourceIdentity) -> list[IdentityMatchCandidate]:
        normalized_system = source_identity.system.strip().lower()
        normalized_external_id = source_identity.external_id.strip().lower()
        matches = []
        for candidate in self._candidates.values():
            for signal in candidate.signals:
                if normalized_system in signal.description.lower() or normalized_external_id in signal.description.lower():
                    matches.append(candidate)
                    break
        return sorted(matches, key=lambda candidate: candidate.confidence_score, reverse=True)

    def save_candidate(self, candidate: IdentityMatchCandidate) -> IdentityMatchCandidate:
        self._candidates[candidate.id] = candidate
        self._persist()
        return candidate

    def get_candidate(self, candidate_id: UUID | str) -> IdentityMatchCandidate | None:
        return self._candidates.get(UUID(str(candidate_id)))

    def get_pending_reviews(self) -> list[IdentityMatchCandidate]:
        return self.list_candidates(IdentityResolutionStatus.NEEDS_REVIEW.value)

    def approve_match(
        self,
        candidate_id: UUID | str,
        decided_by: UUID | None = None,
        notes: str = "",
    ) -> IdentityResolutionDecision:
        return self.record_decision(
            IdentityResolutionDecision(
                candidate_id=UUID(str(candidate_id)),
                status=IdentityResolutionStatus.AUTO_MATCHED.value,
                decided_by=decided_by,
                notes=notes,
            )
        )

    def reject_match(
        self,
        candidate_id: UUID | str,
        decided_by: UUID | None = None,
        notes: str = "",
    ) -> IdentityResolutionDecision:
        return self.record_decision(
            IdentityResolutionDecision(
                candidate_id=UUID(str(candidate_id)),
                status=IdentityResolutionStatus.REJECTED.value,
                decided_by=decided_by,
                notes=notes,
            )
        )

    def merge_entities(self, source_entity_id: UUID | str, target_entity_id: UUID | str) -> None:
        self._history.append(
            {
                "source_entity_id": str(source_entity_id),
                "target_entity_id": str(target_entity_id),
                "status": IdentityResolutionStatus.MERGED.value,
            }
        )
        self._persist()

    def get_resolution_history(self, entity_id: UUID | str) -> list[dict]:
        entity_id_text = str(entity_id)
        return [
            event
            for event in self._history
            if event.get("source_entity_id") == entity_id_text or event.get("target_entity_id") == entity_id_text
        ]

    def list_candidates(self, status: str | None = None) -> list[IdentityMatchCandidate]:
        candidates = list(self._candidates.values())
        if status:
            candidates = [candidate for candidate in candidates if candidate.status == status]
        return sorted(candidates, key=lambda candidate: candidate.confidence_score, reverse=True)

    def record_decision(self, decision: IdentityResolutionDecision) -> IdentityResolutionDecision:
        candidate = self.get_candidate(decision.candidate_id)
        if not candidate:
            raise KeyError(f"Identity match candidate not found: {decision.candidate_id}")
        candidate.status = decision.status
        candidate.updated_at = decision.decided_at
        self._decisions.append(decision)
        self._history.append(
            {
                "candidate_id": str(decision.candidate_id),
                "source_entity_id": str(decision.source_entity_id or candidate.source_entity_id),
                "target_entity_id": str(decision.target_entity_id or candidate.target_entity_id),
                "status": decision.status,
                "decided_by": str(decision.decided_by) if decision.decided_by else None,
                "decided_at": decision.decided_at,
                "notes": decision.notes,
            }
        )
        self._persist()
        return decision

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._candidates = {
            UUID(item["id"]): IdentityMatchCandidate(
                id=UUID(item["id"]),
                source_entity_id=UUID(item["source_entity_id"]),
                target_entity_id=UUID(item["target_entity_id"]),
                source_display_name=item["source_display_name"],
                target_display_name=item["target_display_name"],
                entity_type=item["entity_type"],
                confidence_score=int(item.get("confidence_score", item.get("score", 0))),
                status=item.get("status", IdentityResolutionStatus.PENDING.value),
                signals=[IdentityMatchSignal(**signal) for signal in item.get("signals", [])],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )
            for item in payload.get("candidates", [])
        }
        self._decisions = [
            IdentityResolutionDecision(
                candidate_id=UUID(item["candidate_id"]),
                status=item["status"],
                source_entity_id=UUID(item["source_entity_id"]) if item.get("source_entity_id") else None,
                target_entity_id=UUID(item["target_entity_id"]) if item.get("target_entity_id") else None,
                decided_by=UUID(item["decided_by"]) if item.get("decided_by") else None,
                decided_at=item["decided_at"],
                notes=item.get("notes", ""),
            )
            for item in payload.get("decisions", [])
        ]
        self._history = list(payload.get("history", []))

    def _persist(self) -> None:
        payload = {
            "candidates": [candidate.to_dict() for candidate in self.list_candidates()],
            "decisions": [
                {
                    "candidate_id": str(decision.candidate_id),
                    "status": decision.status,
                    "source_entity_id": str(decision.source_entity_id) if decision.source_entity_id else None,
                    "target_entity_id": str(decision.target_entity_id) if decision.target_entity_id else None,
                    "decided_by": str(decision.decided_by) if decision.decided_by else None,
                    "decided_at": decision.decided_at,
                    "notes": decision.notes,
                }
                for decision in self._decisions
            ],
            "history": self._history,
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

