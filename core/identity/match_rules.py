from __future__ import annotations

from core.entities.entity import EnterpriseEntity
from core.identity.confidence import MATCH_WEIGHTS
from core.identity.identity_match import IdentityMatchSignal, normalize_identity_text


def identity_match_signals(source: EnterpriseEntity, target: EnterpriseEntity) -> list[IdentityMatchSignal]:
    signals: list[IdentityMatchSignal] = []
    signals.extend(_source_reference_signals(source, target))
    signals.extend(_entity_attribute_signals(source, target))
    signals.extend(_ownership_and_tag_signals(source, target))
    return _dedupe_signals(signals)


def _source_reference_signals(source: EnterpriseEntity, target: EnterpriseEntity) -> list[IdentityMatchSignal]:
    signals: list[IdentityMatchSignal] = []
    for source_ref in source.source_systems:
        for target_ref in target.source_systems:
            same_system = source_ref.system.strip().lower() == target_ref.system.strip().lower()
            same_external_id = source_ref.external_id.strip().lower() == target_ref.external_id.strip().lower()
            if same_system and same_external_id:
                signals.append(_signal("exact_source_identity", f"{source_ref.system} source identity matches exactly."))
            elif same_external_id:
                signals.append(_signal("external_id_match", "External IDs match across source systems."))

            source_name = normalize_identity_text(source_ref.external_name)
            target_name = normalize_identity_text(target_ref.external_name)
            if source_name and source_name == target_name:
                signals.append(_signal("normalized_name_match", "Source-system external names normalize to the same value."))

            signals.extend(_attribute_signals(source_ref.attributes, target_ref.attributes))
    return signals


def _entity_attribute_signals(source: EnterpriseEntity, target: EnterpriseEntity) -> list[IdentityMatchSignal]:
    signals: list[IdentityMatchSignal] = []
    source_name = normalize_identity_text(source.display_name)
    target_name = normalize_identity_text(target.display_name)
    if source_name and source_name == target_name:
        signals.append(_signal("normalized_name_match", "Entity display names normalize to the same value."))
    signals.extend(_attribute_signals(source.metadata, target.metadata))
    return signals


def _ownership_and_tag_signals(source: EnterpriseEntity, target: EnterpriseEntity) -> list[IdentityMatchSignal]:
    signals: list[IdentityMatchSignal] = []
    if source.owner_id and source.owner_id == target.owner_id:
        signals.append(_signal("owner_match", "Entities share the same owner."))
    for tag_key in ("application", "app", "service"):
        if _normalized_mapping_value(source.tags, tag_key) and _normalized_mapping_value(source.tags, tag_key) == _normalized_mapping_value(target.tags, tag_key):
            signals.append(_signal("application_tag_match", f"Application tag '{tag_key}' matches."))
    if _normalized_mapping_value(source.tags, "environment") and _normalized_mapping_value(source.tags, "environment") == _normalized_mapping_value(target.tags, "environment"):
        signals.append(_signal("environment_match", "Environment tag matches."))
    if _normalized_mapping_value(source.tags, "vendor") and _normalized_mapping_value(source.tags, "vendor") == _normalized_mapping_value(target.tags, "vendor"):
        signals.append(_signal("vendor_match", "Vendor tag matches."))
    if _normalized_mapping_value(source.tags, "region") and _normalized_mapping_value(source.tags, "region") == _normalized_mapping_value(target.tags, "region"):
        signals.append(_signal("region_match", "Region tag matches."))
    shared_tags = {
        key
        for key, value in source.tags.items()
        if key in target.tags and normalize_identity_text(value) == normalize_identity_text(target.tags[key])
    }
    if shared_tags:
        signals.append(_signal("same_tags", f"Shared matching tags: {', '.join(sorted(shared_tags))}."))
    return signals


def _attribute_signals(source_attributes: dict, target_attributes: dict) -> list[IdentityMatchSignal]:
    signals: list[IdentityMatchSignal] = []
    mappings = {
        "hostname": "hostname_match",
        "fqdn": "hostname_match",
        "ip_address": "ip_address_match",
        "private_ip": "ip_address_match",
        "public_ip": "ip_address_match",
        "cloud_resource_id": "cloud_resource_id_match",
        "resource_id": "cloud_resource_id_match",
        "cloud_account_id": "same_cloud_account",
        "account_id": "same_cloud_account",
    }
    for key, signal_name in mappings.items():
        source_value = _normalized_mapping_value(source_attributes, key)
        target_value = _normalized_mapping_value(target_attributes, key)
        if source_value and source_value == target_value:
            signals.append(_signal(signal_name, f"Attribute '{key}' matches."))
    return signals


def _normalized_mapping_value(mapping: dict, key: str) -> str:
    return normalize_identity_text(str(mapping.get(key, "")))


def _signal(name: str, description: str) -> IdentityMatchSignal:
    return IdentityMatchSignal(name=name, score=MATCH_WEIGHTS[name], description=description)


def _dedupe_signals(signals: list[IdentityMatchSignal]) -> list[IdentityMatchSignal]:
    by_name: dict[str, IdentityMatchSignal] = {}
    for signal in signals:
        if signal.name not in by_name or signal.score > by_name[signal.name].score:
            by_name[signal.name] = signal
    return sorted(by_name.values(), key=lambda item: item.score, reverse=True)

