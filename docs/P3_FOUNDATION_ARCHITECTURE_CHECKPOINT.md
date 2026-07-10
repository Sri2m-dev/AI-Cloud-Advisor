# P3 Foundation Architecture Checkpoint

## Executive Summary

P3.2 through P3.8 now form a coherent in-memory Enterprise Data Fabric foundation: canonical contracts, registries, identity resolution, lineage/provenance, quality/trust scoring, versioning/temporal history, and semantic ontology interfaces. The review found one confirmed foundation defect: lineage and provenance operational records preserved `organization_id` but did not preserve `tenant_id`. P3.9 corrected this with backward-compatible optional `tenant_id` fields on `LineageEvent` and `ProvenanceRecord`.

Persistence is not ready to begin directly. The foundation is stable enough to proceed, but the next phase should define orchestration contracts before repository adapters or database schemas. The recommended next phase is **P3.10B - Orchestration Contracts**.

Go/no-go decision: **NO-GO for persistence adapters now; GO for orchestration-contract design.**

## Reviewed Scope

Packages reviewed:

- `data_fabric/contracts/`
- `data_fabric/registry/`
- `data_fabric/identity/`
- `data_fabric/lineage/`
- `data_fabric/quality/`
- `data_fabric/versioning/`
- `data_fabric/semantic/`

Documents reviewed:

- `docs/P3_CANONICAL_CONTRACTS.md`
- `docs/P3_REGISTRY_INTERFACES.md`
- `docs/P3_IDENTITY_RESOLUTION.md`
- `docs/P3_LINEAGE_PROVENANCE.md`
- `docs/P3_DATA_QUALITY_TRUST.md`
- `docs/P3_VERSIONING_TEMPORAL_HISTORY.md`
- `docs/P3_SEMANTIC_ONTOLOGY.md`
- `docs/NEXORA_DATA_FABRIC.md`
- `docs/NEXORA_DOMAIN_MODEL.md`
- `docs/NEXORA_ENTERPRISE_ARCHITECTURE.md`
- ADR-008 through ADR-015

## Current Package Map

| Package | Ownership |
| --- | --- |
| `contracts` | Canonical entity, relationship, identity, lineage, provenance, version, quality, ownership contracts. |
| `registry` | Entity and relationship registration/query interfaces plus in-memory stores. |
| `identity` | Source identity candidate matching and no-match/duplicate decisions. |
| `lineage` | Explainability events and provenance records. |
| `quality` | Quality dimensions, rule evaluation, and trust scoring. |
| `versioning` | Immutable snapshots, temporal records, deterministic hashing, and comparison. |
| `semantic` | Ontology concepts, taxonomy, and source-term semantic mapping. |

## Model-Overlap Matrix

| Overlap | Classification | Finding |
| --- | --- | --- |
| `EntityVersion` vs `VersionRecord` | Intentional contract vs operational model | `EntityVersion` is metadata attached to canonical entities; `VersionRecord` is immutable snapshot state. Acceptable. |
| `EntityQuality` vs `QualityAssessment` | Intentional contract vs operational result | `EntityQuality` is embedded source quality; `QualityAssessment` is evaluator output. Acceptable. |
| `EntityLineage` vs `LineageEvent` / `LineagePath` | Intentional contract vs operational trace | Embedded lineage summarizes source movement; events/path support explainability. Acceptable. |
| `EntityProvenance` vs `ProvenanceRecord` | Intentional contract vs operational record | Embedded provenance is fact-level context; records support trace queries. Acceptable. |
| `EntityIdentity` vs identity result models | Intentional contract vs matching result | Identity contract records source identity; match models describe resolution attempts. Acceptable. |
| `EnterpriseRelationship` vs `ConceptRelationship` | Distinct domains | Enterprise relationships connect enterprise entities; concept relationships connect ontology concepts. No defect. |
| `EntityType` vs semantic concept types | Acceptable duplication | Entity type classifies canonical records; concept type classifies ontology concepts. Needs documentation during persistence mapping. |
| `confidence_score` vs `TrustScore` | Naming risk, not defect | Entity confidence is 0-1; trust score is 0-100. Meaning is distinct but must be documented in persistence schema. |
| `quality_score` vs `QualityAssessment` score | Naming risk, not defect | Embedded 0-1 score and assessment 0-100 score are distinct. Needs clear schema names. |
| metadata / attributes / tags / aliases / synonyms / payload | Serialization risk | Flexible fields are useful but require a shared serializer and JSON-column policy before persistence. |

## Naming-Consistency Matrix

| Field | Status | Notes |
| --- | --- | --- |
| `organization_id` | Consistent | Present across tenant-scoped records. Mandatory in canonical and operational records. |
| `tenant_id` | Mostly consistent | Optional in dataclasses, but stores partition by explicit value including `None`. Persistence must decide whether `None` is allowed. |
| `source_system` | Consistent | Used for original system identity and mapping source. |
| `source_identifier` | Consistent | Used with `source_system`; nullable on relationships but required by registry validation. |
| `canonical_id` | Consistent | Entity-level canonical identifier; not present on relationships or semantic concepts. |
| `entity_id` | Consistent | Canonical entity subject id or relationship endpoint. |
| `relationship_id` | Consistent | Enterprise relationship id or ontology relationship id contextually. |
| `concept_id` | Consistent | Semantic ontology identifier, intentionally separate from entity ids. |
| `version` | Consistent but contextual | Contract version and snapshot version are aligned but not identical persistence columns. |
| `recorded_at` | Consistent | Versioning/temporal capture time. |
| `effective_from` / `effective_to` | Consistent | Effective-time window, primarily versioning. |
| `created_at` / `updated_at` | Consistent | Canonical record timestamps, validated by quality rules. |
| `confidence_score` | 0-1 scale | Canonical/source confidence. |
| `quality_score` | 0-1 scale | Embedded canonical quality signal. |

No confirmed naming defect requires code correction beyond the tenant-scope hardening listed below.

## Responsibility-Ownership Matrix

| Responsibility | Owner |
| --- | --- |
| Canonical record shape | `contracts` |
| Entity/relationship lookup and registration | `registry` |
| Source identity resolution | `identity` |
| Semantic concept mapping | `semantic` |
| Quality scoring and gating signal | `quality` |
| Version comparison and immutable history | `versioning` |
| Source-to-canonical explainability | `lineage` |
| Persistence write orchestration | Not yet defined |
| Transaction/idempotency policy | Not yet defined |

## Dependency-Direction Review

The intended direction is preserved: `contracts` does not import registry, identity, lineage, quality, versioning, or semantic packages. Sibling packages import contracts or their own package-local models. No dashboard, connector, database, Supabase, scheduler, or Knowledge Graph dependency was found in the Data Fabric packages.

## Tenant-Isolation Findings

All P3 packages now preserve `organization_id` and `tenant_id` where state is tenant-scoped. P3.9 corrected lineage/provenance operational records so explainability data can carry tenant context before persistence. In-memory stores partition records by organization and tenant. Batch quality output includes organization context in result keys. The primary open question is whether `tenant_id=None` should remain valid after persistence. Recommendation: define a tenant-context policy before schema work.

## Immutability Findings

- Registry reads defensively copy records.
- Identity resolver copies stored entities and result entities.
- Lineage/provenance trackers return immutable or copied records.
- Quality result models use frozen dataclasses and read-only mappings.
- Version snapshots recursively freeze payloads.
- Semantic concepts and mappings freeze attributes.

Canonical contracts themselves still expose mutable `tags` and `metadata`, which is acceptable for source contracts but requires defensive copy at persistence boundaries.

## Serialization Findings

Versioning contains the strongest deterministic serialization behavior, including dataclasses, enums, UUIDs, datetimes, tuples, sets, nested dictionaries, and frozen payloads. This should become the seed for a shared serializer contract before persistence. Do not duplicate serializer behavior in each repository adapter.

Serializer decision: **shared deterministic serializer required before persistence adapters.**

## Time-Semantics Findings

- Canonical contracts default timestamps to timezone-aware UTC.
- Versioning distinguishes `recorded_at` from `effective_from` / `effective_to`.
- Point-in-time lookup uses closed-open intervals.
- Quality validates `created_at <= updated_at`.
- Freshness is currently timestamp-availability based, not age-policy based.

Persistence should enforce timezone-aware UTC and reject naive datetimes at repository boundaries.

## Score-Semantics Findings

| Score | Range | Meaning |
| --- | ---: | --- |
| `confidence_score` | 0-1 | Confidence in canonical entity or relationship. |
| `quality_score` | 0-1 | Embedded quality signal on canonical record. |
| `EntityQuality.trust_score` | 0-1 | Embedded contract-level trust summary. |
| `MatchResult.confidence_score` | 0-1 | Identity resolution confidence. |
| `SemanticMapping.confidence` | 0-100 | Semantic mapping confidence. |
| `TrustScore.final_score` | 0-100 | Weighted quality/trust assessment result. |
| lineage confidence | 0-100 dimension | Quality dimension derived from lineage availability/evidence. |

Decision: keep both ranges, but persistence schema must name 0-100 fields explicitly, for example `trust_score_100` or documented 0-100 columns.

## Exception-Hierarchy Findings

Each package has package-local base exceptions. This is catchable today, but callers cannot catch one shared Data Fabric base error.

Exception decision: **shared `DataFabricError` is recommended before broad service orchestration**, but not required as an immediate code correction in this checkpoint.

## Orchestration Gaps

Persistence should not begin before defining:

- canonicalization pipeline
- entity-ingestion coordinator
- unit-of-work boundary
- transaction boundary
- registry plus identity plus semantic orchestration
- quality gate policy
- lineage emission policy
- version-creation policy
- idempotency contract
- batch-processing result contract

## Persistence-Readiness Assessment

| Question | Checkpoint Answer |
| --- | --- |
| What is the aggregate root? | Canonical entity and canonical relationship, with tenant-scoped registry state. |
| Which records are immutable? | Version snapshots, temporal records, lineage events, provenance records, quality assessments, semantic value results. |
| Which records are mutable? | Current registry state and active semantic concepts/mappings through explicit update/deactivate methods. |
| What is authoritative: registry state or version history? | Registry state is current operational view; version history is immutable audit/history. Need orchestration policy. |
| When is a new entity version created? | On material canonical payload change, except explicit unchanged-version allowance. Need write-flow policy. |
| How are relationships versioned? | Same version snapshot mechanism as entities. |
| How are soft deletes represented? | Registry and semantic packages use deactivation flags; persistence policy needs a common soft-delete convention. |
| Which uniqueness constraints are required? | Tenant-scoped ids, canonical ids, source identity pairs, semantic canonical names, mapping ids, version numbers. |
| Which indexes will be required? | Organization/tenant plus id, canonical_id, source pair, version, effective-time windows, concept name/synonym. |
| Which operations require transactions? | Registry update plus identity/semantic resolution plus lineage/provenance/version writes. |
| Which writes must be idempotent? | Ingestion batches, entity registration, relationship registration, lineage/provenance emission, snapshot creation. |
| How will optimistic concurrency be handled? | Not yet defined. Needs orchestration contracts. |
| How will tenant isolation be enforced at storage level? | Composite tenant keys and row-level access policy. Needs persistence architecture. |
| Which fields need JSON storage versus normalized columns? | Flexible metadata/attributes/payload likely JSON; identifiers, tenant keys, types, source ids, scores, timestamps should be columns. |

## Required Corrections

- `LineageEvent` now includes optional `tenant_id` to preserve tenant context in explainability events.
- `ProvenanceRecord` now includes optional `tenant_id` to preserve tenant context in source authority records.

These are backward-compatible contract hardening changes. Existing validation still requires `organization_id`; tenant requirement policy remains deferred to orchestration/persistence design.

## Deferred Improvements

- Add shared Data Fabric exception base.
- Add shared deterministic serializer contract based on versioning canonicalization.
- Add shared tenant-context value object or policy.
- Define orchestration/write-flow contracts before persistence.
- Define score naming policy for 0-1 versus 0-100 fields.
- Define timezone validation helper for persistence boundaries.

## Recommended Next Phase

**P3.10B - Orchestration Contracts**.

Rationale: foundational models are stable, but write ownership, transaction/idempotency boundaries, quality gate timing, version creation policy, and lineage emission policy are not defined strongly enough for persistence adapters.

## Go/No-Go Decision

- Model foundation: **GO WITH CONDITIONS**
- Persistence adapters now: **NO-GO**
- Orchestration contracts next: **GO**


