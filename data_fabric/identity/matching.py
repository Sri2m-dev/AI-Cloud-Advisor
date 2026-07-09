"""Identity matching primitives for canonical entity resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from data_fabric.contracts import EnterpriseEntity


class MatchDecision(str, Enum):
    """Resolution outcome for an identity match attempt."""

    MATCH = "match"
    DUPLICATE = "duplicate"
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    """Source identity attributes to resolve against canonical entities."""

    source_system: str
    source_identifier: str
    name: str
    organization_id: str
    canonical_id: str | None = None
    tenant_id: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result returned by an identity resolver."""

    decision: MatchDecision
    candidate: MatchCandidate
    confidence_score: float
    match_reason: str
    matched_entity: EnterpriseEntity | None = None
    matched_entities: tuple[EnterpriseEntity, ...] = field(default_factory=tuple)

    @property
    def is_match(self) -> bool:
        return self.decision is MatchDecision.MATCH

    @property
    def is_duplicate(self) -> bool:
        return self.decision is MatchDecision.DUPLICATE


def normalize_name(value: str) -> str:
    """Normalize a human-readable name for deterministic in-memory matching."""

    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def entity_aliases(entity: EnterpriseEntity) -> tuple[str, ...]:
    aliases = list(entity.metadata.get("aliases", []))
    if entity.identity is not None:
        aliases.extend(entity.identity.aliases)
    return tuple(str(alias) for alias in aliases if alias)


def candidate_aliases(candidate: MatchCandidate) -> tuple[str, ...]:
    aliases = list(candidate.aliases)
    metadata_aliases = candidate.metadata.get("aliases", [])
    if isinstance(metadata_aliases, (list, tuple, set)):
        aliases.extend(str(alias) for alias in metadata_aliases)
    return tuple(alias for alias in aliases if alias)


def score_match(candidate: MatchCandidate, entity: EnterpriseEntity) -> tuple[float, str]:
    """Score one candidate against one canonical entity."""

    if candidate.organization_id != entity.organization_id:
        return 0.0, "organization_mismatch"

    if candidate.canonical_id and candidate.canonical_id == entity.canonical_id:
        return 1.0, "canonical_id"

    if (
        candidate.source_system == entity.source_system
        and candidate.source_identifier == entity.source_identifier
    ):
        return 0.98, "source_identity"

    candidate_name = normalize_name(candidate.name)
    entity_name = normalize_name(entity.name)
    if candidate_name and candidate_name == entity_name:
        return 0.86, "normalized_name"

    candidate_alias_names = {normalize_name(alias) for alias in candidate_aliases(candidate)}
    entity_alias_names = {normalize_name(alias) for alias in entity_aliases(entity)}
    if candidate_name and candidate_name in entity_alias_names:
        return 0.82, "candidate_name_entity_alias"
    if entity_name and entity_name in candidate_alias_names:
        return 0.82, "entity_name_candidate_alias"
    if candidate_alias_names.intersection(entity_alias_names):
        return 0.8, "alias"

    return 0.0, "no_match"
