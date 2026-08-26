# PUE-010 — Universal Evidence Shadow Integration & Certification

## Authority boundary

PUE-010 is an independently callable, in-memory, non-authoritative orchestration layer. The existing prospect pipeline remains authoritative. The shadow package imports no Streamlit page, prospect service, database adapter, enterprise registry, or production repository. It neither reads nor writes application session state.

The orchestrator accepts authorized evidence bytes, a PUE-003 decision repository, effective mappings, and explicitly authorized source-row values. It does not manufacture confirmation decisions or extract governed values from raw bytes. This preserves the boundary between structural observation and governed row access.

## Certified flow

1. PUE-001 profiles the authorized bytes per file and sheet.
2. PUE-002 forms semantic candidates over the profile.
3. PUE-010 verifies that each supplied mapping is currently effective and bound to the current discovery fingerprint.
4. PUE-004 normalizes only values attached to those effective mappings.
5. PUE-005/C5A produces coverage, capability, alignment, and current execution authorization metadata.
6. PUE-008 interprets a bounded question against the current governed catalog.
7. PUE-007 constructs a governed plan and request.
8. PUE-006 executes only a READY request with current authorization.
9. PUE-009 composes only the certified result, or a governed blocked/unsupported explanation.

Every stage reports `COMPLETED`, `PARTIAL`, `BLOCKED`, `SKIPPED`, `FAILED`, or `NOT_APPLICABLE`. A blocked governance stage skips normalization and capability. A non-interpreted question skips planning and execution. A non-READY plan skips execution.

## Provenance and replay

The result chain carries the source/file identity, structural and semantic fingerprints, mapping decisions, normalization runs, capability assessment, execution authorizations, interpretation, analytical plan, aggregation result, and answer. Scope originates in evidence provenance; absent tenant or organization identifiers remain absent. Fingerprints exclude operational timing so equivalent certified inputs replay deterministically.

## Non-interference and retention

Shadow artifacts are held in a disposable `InMemoryShadowRepository`. They are returned explicitly and may be purged by analysis. Purge removes the local shadow analysis, question results, and runtime repositories. It does not mutate the caller-owned governance repository or any production store. Legacy values may be compared by reference, but are never supplied to PUE stages.

## Activation readiness

Recommendation: `READY_FOR_LIMITED_SHADOW` only.

Activation blockers:

- Production persistence and purge integration are not certified.
- Confirmation UX is not integrated.
- Multi-file fusion is unavailable.
- Natural-language vocabulary and analytical operations remain intentionally bounded.
- Entity resolution, production observability, and rollback are unavailable.
- No production Ask Nexora, UI, or prospect-path activation exists.

Completion of PUE-010 does not authorize activation.

## Known limitations

- Governed source-row values must be supplied by an authorized reader; PUE-010 does not add one.
- Currency-grouped execution exists upstream, but there is no dedicated natural-language planning route.
- Separate files are independently profileable but are not fused.
- Performance observations are diagnostic only and establish no production SLA.
