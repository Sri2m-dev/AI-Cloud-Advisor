# P4.3.2 Relationship Intelligence

## Contract

The milestone extends the P3 relationship enum additively for the authorized
enterprise vocabulary and adds evidence/discovery/validation references to the
canonical relationship contract. Existing values, identities, persistence, RLS,
versioning, lineage, and provenance are preserved.

## APIs

- `get_relationships`
- `get_dependencies`
- `get_owners`
- `get_consumers`
- `get_providers`
- `get_impact`
- `get_blast_radius`
- `traverse` for 1, 2, 3, or N hops

Traversal is deterministic breadth-first search with cycle protection. Direction and
relationship type filters are explicit. Narratives count only resolved canonical
endpoints supported by evidence-backed edges.

## Runtime and persistence

Supabase reads the existing P3 `data_fabric.enterprise_relationships` table with
composite tenant predicates. Development automatically selects a safe SQLite
projection and treats a missing local store as empty. Production invalid
configuration fails closed. No schema migration is required.

## Workspace

Relationship Explorer provides canonical entity search, direction and depth filters,
dependency/impact/ownership views, bounded expansion, metrics, evidence disclosure,
and an executive impact summary. It is authenticated and available to the same
governed read personas as Enterprise Registry.

## Limitations

The DEV baseline may contain canonical cloud-account entities without governed P3
relationship edges. The explorer reports that state as empty and never fabricates a
relationship. Connector/CMDB relationship ingestion remains a separate governed write
workflow.

## Certification

- Focused relationship and registry tests: 26 passed.
- P3 registry/repository tests: 107 passed.
- Protected persona, audit, classification, FG-001, and FG-002 tests: 76 passed.
- PVT-003: 60 passed, 2 skipped.
- Full suite: 840 passed, 7 skipped.
- Governance, compatibility, Ruff, compile/import, dependency, and diff checks passed.
- DEV: 67 canonical entities; account `727482365532` resolved to
  `cloud_account:e099f2ab-32d7-5f50-b03a-364c78d60098`; zero governed relationships;
  explicit no-impact narrative.

Automated Streamlit empty-state UI coverage passed. Manual in-app browser control was
unavailable at the browser connection boundary during certification, so visual browser
certification remains pending and is not represented as passed.
