"""Deterministic version comparison utilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from data_fabric.versioning.interfaces import VersionComparator
from data_fabric.versioning.models import (
    VersionComparison,
    VersionDifference,
    VersionRecord,
    to_canonical_value,
)


class DeterministicVersionComparator(VersionComparator):
    """Compare snapshot payloads with stable output ordering."""

    def compare(self, first: VersionRecord, second: VersionRecord) -> VersionComparison:
        differences = tuple(_compare_values(first.payload, second.payload, "$"))
        return VersionComparison(
            first_id=first.snapshot_id,
            second_id=second.snapshot_id,
            differences=differences,
        )


def _compare_values(first: Any, second: Any, path: str) -> list[VersionDifference]:
    first = to_canonical_value(first)
    second = to_canonical_value(second)
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        return _compare_mappings(first, second, path)
    if _is_sequence(first) and _is_sequence(second):
        return _compare_sequences(first, second, path)
    if first != second:
        return [VersionDifference(path=path, change_type="changed", old_value=first, new_value=second)]
    return []


def _compare_mappings(first: Mapping[str, Any], second: Mapping[str, Any], path: str) -> list[VersionDifference]:
    differences: list[VersionDifference] = []
    first_keys = set(first)
    second_keys = set(second)
    for key in sorted(first_keys - second_keys, key=str):
        differences.append(VersionDifference(path=f"{path}.{key}", change_type="removed", old_value=first[key], new_value=None))
    for key in sorted(second_keys - first_keys, key=str):
        differences.append(VersionDifference(path=f"{path}.{key}", change_type="added", old_value=None, new_value=second[key]))
    for key in sorted(first_keys & second_keys, key=str):
        differences.extend(_compare_values(first[key], second[key], f"{path}.{key}"))
    return sorted(differences, key=lambda item: (item.path, item.change_type))


def _compare_sequences(first: Sequence[Any], second: Sequence[Any], path: str) -> list[VersionDifference]:
    differences: list[VersionDifference] = []
    shared_len = min(len(first), len(second))
    for index in range(shared_len):
        differences.extend(_compare_values(first[index], second[index], f"{path}[{index}]"))
    for index in range(shared_len, len(first)):
        differences.append(VersionDifference(path=f"{path}[{index}]", change_type="removed", old_value=first[index], new_value=None))
    for index in range(shared_len, len(second)):
        differences.append(VersionDifference(path=f"{path}[{index}]", change_type="added", old_value=None, new_value=second[index]))
    return sorted(differences, key=lambda item: (item.path, item.change_type))


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray)
