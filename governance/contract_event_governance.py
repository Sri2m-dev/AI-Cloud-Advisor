"""Contract and event governance primitives for versioned compatibility gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class GovernanceValidationError(ValueError):
    """Raised when a contract manifest or payload violates governance policy."""


class ChangeLevel(str, Enum):
    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


@dataclass(frozen=True, order=True, slots=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        if min(self.major, self.minor, self.patch) < 0:
            raise GovernanceValidationError("semantic version components cannot be negative")

    @classmethod
    def parse(cls, value: str) -> "SemanticVersion":
        parts = str(value).split(".")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise GovernanceValidationError("version must use MAJOR.MINOR.PATCH")
        return cls(*(int(part) for part in parts))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def change_from(self, previous: "SemanticVersion") -> ChangeLevel:
        if self <= previous:
            return ChangeLevel.NONE
        if self.major != previous.major:
            return ChangeLevel.MAJOR
        if self.minor != previous.minor:
            return ChangeLevel.MINOR
        return ChangeLevel.PATCH


@dataclass(frozen=True, slots=True)
class FieldSchema:
    name: str
    type_name: str
    required: bool = True
    enum_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.type_name.strip():
            raise GovernanceValidationError("field name and type are required")
        if len(set(self.enum_values)) != len(self.enum_values):
            raise GovernanceValidationError(f"duplicate enum value for field {self.name}")


@dataclass(frozen=True, slots=True)
class DeprecationNotice:
    field_name: str
    since_version: SemanticVersion
    removal_version: SemanticVersion
    replacement: str

    def __post_init__(self) -> None:
        if not self.field_name.strip() or not self.replacement.strip():
            raise GovernanceValidationError("deprecation field and replacement are required")
        if self.removal_version.major <= self.since_version.major:
            raise GovernanceValidationError(
                "deprecated fields require at least one major-version removal window"
            )


@dataclass(frozen=True, slots=True)
class ContractManifest:
    contract_id: str
    kind: str
    version: SemanticVersion
    provider: str
    fields: tuple[FieldSchema, ...]
    deprecations: tuple[DeprecationNotice, ...] = ()

    def __post_init__(self) -> None:
        if not self.contract_id.strip() or not self.provider.strip():
            raise GovernanceValidationError("contract_id and provider are required")
        if self.kind not in {"contract", "event"}:
            raise GovernanceValidationError("kind must be contract or event")
        names = [item.name for item in self.fields]
        if len(names) != len(set(names)):
            raise GovernanceValidationError("field names must be unique")
        known = set(names)
        for notice in self.deprecations:
            if notice.field_name not in known:
                raise GovernanceValidationError(
                    f"deprecated field is not present: {notice.field_name}"
                )

    @property
    def field_map(self) -> dict[str, FieldSchema]:
        return {item.name: item for item in self.fields}

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        for item in self.fields:
            if item.required and item.name not in payload:
                raise GovernanceValidationError(f"required field missing: {item.name}")
            if item.name not in payload:
                continue
            value = payload[item.name]
            if not _matches_type(value, item.type_name):
                raise GovernanceValidationError(f"field {item.name} must be {item.type_name}")
            if item.enum_values and value not in item.enum_values:
                raise GovernanceValidationError(f"unsupported {item.name}: {value}")


@dataclass(frozen=True, slots=True)
class ConsumerRequirement:
    consumer: str
    contract_id: str
    minimum_version: SemanticVersion
    required_fields: Mapping[str, str] = field(default_factory=dict)

    def verify(self, provider: ContractManifest) -> None:
        if provider.contract_id != self.contract_id:
            raise GovernanceValidationError("consumer/provider contract mismatch")
        if provider.version < self.minimum_version:
            raise GovernanceValidationError("provider version is below consumer minimum")
        for name, type_name in self.required_fields.items():
            field_schema = provider.field_map.get(name)
            if field_schema is None:
                raise GovernanceValidationError(f"consumer field missing: {name}")
            if field_schema.type_name != type_name:
                raise GovernanceValidationError(f"consumer field type changed: {name}")


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    required_change: ChangeLevel
    declared_change: ChangeLevel
    compatible: bool
    reasons: tuple[str, ...]


def assess_compatibility(
    previous: ContractManifest, current: ContractManifest
) -> CompatibilityResult:
    if previous.contract_id != current.contract_id or previous.kind != current.kind:
        raise GovernanceValidationError("only matching contract identities can be compared")
    if previous.provider != current.provider:
        raise GovernanceValidationError("provider ownership cannot change without governance")

    reasons: list[str] = []
    required = ChangeLevel.NONE
    previous_fields = previous.field_map
    current_fields = current.field_map

    for name, old in previous_fields.items():
        new = current_fields.get(name)
        if new is None:
            required = ChangeLevel.MAJOR
            reasons.append(f"field removed: {name}")
            continue
        if old.type_name != new.type_name or (not old.required and new.required):
            required = ChangeLevel.MAJOR
            reasons.append(f"breaking field change: {name}")
        removed_values = set(old.enum_values) - set(new.enum_values)
        if removed_values:
            required = ChangeLevel.MAJOR
            reasons.append(f"enum values removed from {name}: {sorted(removed_values)}")
        elif set(new.enum_values) - set(old.enum_values) and required is not ChangeLevel.MAJOR:
            required = ChangeLevel.MINOR
            reasons.append(f"enum values added to {name}")

    for name, new in current_fields.items():
        if name not in previous_fields:
            level = ChangeLevel.MAJOR if new.required else ChangeLevel.MINOR
            if level is ChangeLevel.MAJOR or required is ChangeLevel.NONE:
                required = level
            reasons.append(f"{'required' if new.required else 'optional'} field added: {name}")

    if not reasons and previous != current:
        required = ChangeLevel.PATCH
        reasons.append("non-structural manifest change")

    declared = current.version.change_from(previous.version)
    compatible = _change_rank(declared) >= _change_rank(required)
    if declared is ChangeLevel.NONE and previous != current:
        compatible = False
        reasons.append("manifest changed without a version increment")
    return CompatibilityResult(required, declared, compatible, tuple(reasons))


def _change_rank(level: ChangeLevel) -> int:
    return {
        ChangeLevel.NONE: 0,
        ChangeLevel.PATCH: 1,
        ChangeLevel.MINOR: 2,
        ChangeLevel.MAJOR: 3,
    }[level]


def _matches_type(value: Any, type_name: str) -> bool:
    types_by_name = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": Mapping,
        "array": (list, tuple),
    }
    expected = types_by_name.get(type_name)
    if expected is None:
        raise GovernanceValidationError(f"unsupported schema type: {type_name}")
    if type_name in {"integer", "number"} and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def manifest_from_mapping(value: Mapping[str, Any]) -> ContractManifest:
    """Build and validate a provider manifest from JSON-compatible content."""
    deprecations = tuple(
        DeprecationNotice(
            field_name=item["field_name"],
            since_version=SemanticVersion.parse(item["since_version"]),
            removal_version=SemanticVersion.parse(item["removal_version"]),
            replacement=item["replacement"],
        )
        for item in value.get("deprecations", ())
    )
    fields = tuple(
        FieldSchema(
            name=item["name"],
            type_name=item["type"],
            required=item.get("required", True),
            enum_values=tuple(item.get("enum_values", ())),
        )
        for item in value["fields"]
    )
    return ContractManifest(
        contract_id=value["contract_id"],
        kind=value["kind"],
        version=SemanticVersion.parse(value["version"]),
        provider=value["provider"],
        fields=fields,
        deprecations=deprecations,
    )


def consumer_from_mapping(value: Mapping[str, Any]) -> ConsumerRequirement:
    """Build a consumer requirement from JSON-compatible content."""
    return ConsumerRequirement(
        consumer=value["consumer"],
        contract_id=value["contract_id"],
        minimum_version=SemanticVersion.parse(value["minimum_version"]),
        required_fields=dict(value.get("required_fields", {})),
    )
