"""Canonical normalizer registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from connector_normalization.normalizer import CanonicalNormalizer


@dataclass
class NormalizerRegistry:
    """In-memory registry for canonical normalizers."""

    _normalizers: dict[str, CanonicalNormalizer] = field(default_factory=dict)
    _source_map: dict[str, str] = field(default_factory=dict)

    def register_normalizer(self, normalizer: CanonicalNormalizer, *, sources: tuple[str, ...] = ()) -> CanonicalNormalizer:
        self._normalizers[normalizer.normalizer_id] = normalizer
        for source in sources or normalizer.supported_sources:
            self._source_map[source] = normalizer.normalizer_id
        return normalizer

    def get_normalizer(self, normalizer_id: str) -> CanonicalNormalizer | None:
        return self._normalizers.get(normalizer_id)

    def get_for_source(self, source_system: str) -> CanonicalNormalizer | None:
        normalizer_id = self._source_map.get(source_system)
        return self._normalizers.get(normalizer_id) if normalizer_id else None

    def list_normalizers(self) -> list[CanonicalNormalizer]:
        return list(self._normalizers.values())

    def clear(self) -> None:
        self._normalizers.clear()
        self._source_map.clear()


normalizer_registry = NormalizerRegistry()
