"""Immutable Stage 1/2 pilot display contracts without analytical values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from universal_evidence.capability import CapabilityScope


class PilotVisibility(str, Enum):
    HIDDEN = "HIDDEN"
    DISCOVERY = "DISCOVERY"
    DISCOVERY_AND_CAPABILITY = "DISCOVERY_AND_CAPABILITY"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PilotAnalysisContext:
    scope: CapabilityScope
    prospect_analysis_fingerprint: str
    shadow_fingerprint: str


@dataclass(frozen=True, slots=True)
class EvidenceViewItem:
    concept_id: str
    label: str
    state: str
    state_label: str
    reason: str


@dataclass(frozen=True, slots=True)
class CapabilityViewItem:
    capability_id: str
    label: str
    state: str
    state_label: str
    reason: str


@dataclass(frozen=True, slots=True)
class PilotDetails:
    source_count: int
    sheet_count: int
    record_count: int | None
    mapping_count: int
    normalization_run_count: int


@dataclass(frozen=True, slots=True)
class PuePilotViewModel:
    visibility: PilotVisibility
    scope: CapabilityScope
    pilot_label: str
    authority_caption: str
    evidence_heading: str | None
    evidence_items: tuple[EvidenceViewItem, ...]
    capability_heading: str | None
    capability_items: tuple[CapabilityViewItem, ...]
    details: PilotDetails | None
    safe_message: str | None
    activation_fingerprint: str
    shadow_fingerprint: str | None
    fingerprint: str
