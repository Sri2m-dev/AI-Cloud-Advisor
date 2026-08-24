from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from data_fabric.foundation import TenantContext


@dataclass(frozen=True, slots=True)
class SearchRequest:
    tenant_context: TenantContext
    query_text: str = ""
    entity_types: tuple[str, ...] = ()
    filters: Mapping[str, Any] = field(default_factory=dict)
    result_limit: int = 25
    offset: int = 0
    include_classification: bool = True
    include_financial: bool = False
    include_relationships: bool = False
    include_evidence: bool = False
    temporal_context: Mapping[str, Any] = field(default_factory=dict)
    authorization_scope: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    canonical_id: str
    entity_type: str
    display_name: str
    source_id: str
    aliases: tuple[str, ...]
    matched_fields: tuple[str, ...]
    match_reason: str
    relevance_score: float
    classification_state: str
    confidence: float
    owner: str | None
    business_context: str | None
    financial_summary: Mapping[str, Any]
    relationship_summary: Mapping[str, Any]
    freshness: str
    source_reference: str
    provenance_reference: str | None
    lifecycle: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchResponse:
    tenant_id: str
    query_text: str
    results: tuple[SearchResult, ...]
    total_matches: int
    offset: int
    result_limit: int
    partial: bool
    partial_reasons: tuple[str, ...] = ()
