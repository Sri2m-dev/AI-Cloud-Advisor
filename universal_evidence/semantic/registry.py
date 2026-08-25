"""Versioned in-memory semantic concept registry."""

from __future__ import annotations

from dataclasses import dataclass

from universal_evidence.semantic.models import ConceptDefinition
from universal_evidence.semantic.signals import normalize_text


@dataclass(frozen=True, slots=True)
class ConceptRegistry:
    ontology_version: str
    concepts: tuple[ConceptDefinition, ...]

    def __post_init__(self) -> None:
        identifiers = [item.concept.concept_id for item in self.concepts]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("concept identifiers must be unique")

    def alias_index(self) -> dict[str, tuple[ConceptDefinition, ...]]:
        index: dict[str, list[ConceptDefinition]] = {}
        for definition in self.concepts:
            for alias in definition.concept.aliases:
                index.setdefault(normalize_text(alias), []).append(definition)
        return {key: tuple(value) for key, value in index.items()}
