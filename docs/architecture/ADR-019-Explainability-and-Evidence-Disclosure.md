# ADR-019: Explainability and Evidence Disclosure

Status: Accepted
Date: 2026-07-24
Program: Program G — WP-009/WP-010
Decision authority: Srikanth Mudaliar, Owner, Chief Architect, Program Sponsor

## Context

Dependency and impact answers are unsafe when consumers cannot distinguish
governed facts from derived conclusions, identify the path and evidence used,
or see that evidence is missing, stale, unauthorized, or truncated. Nexora
already has lineage, provenance, versioning, quality/trust, and explicit
freshness semantics. Governed queries must reuse those contracts rather than
create synthetic proof or a second evidence authority.

## Decision

Every explainable query result must disclose enough governed context to inspect
and, when retained history permits, reproduce the result.

An explanation identifies:

- source and affected canonical entities;
- ordered relationships and paths supporting the result;
- authorized evidence references;
- lineage and provenance references where available;
- projection checkpoint sequence and state hash;
- canonical versions where available;
- query/evaluation timestamp and supported effective/as-of time;
- freshness, completeness, truncation, and partial-result state.

## Evidence Authorization

- Evidence disclosure requires `TenantContext`.
- Every evidence reference must match the requesting organization and tenant.
- Authorization to view a graph path does not grant authorization to evidence
  referenced by that path.
- Unauthorized evidence is rejected or omitted with an explicit partial-result
  disclosure; its contents and identifying secrets are never returned.
- Service-role or backend authority is not delegated to query consumers.

## Freshness and Missing Evidence

Where freshness applies, evidence uses the shared states:

- `AVAILABLE`;
- `STALE`;
- `MISSING`.

The result discloses evidence observation time, evaluation time, applicable
freshness threshold, and freshness determination. Stale or missing evidence is
never represented as fresh.

Missing evidence is explicit. It is never fabricated, converted to zero,
treated as confidence, or replaced by synthetic proof. A result may remain
useful with missing evidence only when it is marked incomplete or partial.

## Fact and Inference Boundary

- Canonical entities, relationships, and retained evidence are facts within
  their governed version and temporal scope.
- Dependency reachability, impact sets, summaries, and conclusions are derived
  inferences.
- Every derived inference identifies the governed paths and evidence that
  support it.
- Confidence or quality values describe supplied governed signals; they do not
  create authority or evidence.

## Reproducibility

Explanations include:

- normalized query parameters;
- stable result and path ordering;
- projection/checkpoint identity;
- object versions and temporal scope where available;
- query timestamp;
- limits, consumed budget, and truncation reason;
- evidence references and freshness state.

Equivalent queries over equivalent retained governed state must produce
equivalent explanations. If historical state is unavailable, the result must
say that reproduction is not supported rather than silently use current state.

## Partial Results

`partial=true` is mandatory when any applicable result is incomplete because
of:

- traversal, fan-out, result, or work-budget truncation;
- stale or missing evidence;
- authorized evidence omission;
- unavailable optional lineage/provenance;
- unavailable retained history for a requested explanation.

The result lists deterministic partial reasons. Partial results must not be
presented as complete.

## Compatibility and Reuse

This decision reuses Data Fabric lineage, provenance, versioning, quality/trust,
WP-007 freshness semantics, and WP-008 projection/checkpoint controls. It
defines disclosure behavior only; it does not create an evidence registry,
change canonical authority, prescribe storage, or select a public API.

WP-010 may govern durable evidence packages and case roles under this ADR, but
WP-009 remains limited to query and disclosure contracts over supplied governed
references.

## Consequences

Consumers can distinguish facts from inference and see missing, stale,
unauthorized, or truncated support. Results carry more metadata, but this is a
required correctness and authorization boundary rather than optional
presentation detail.

## Implementation Acceptance

Evidence must cover authorized evidence retrieval, cross-tenant rejection,
freshness and temporal disclosure, missing/stale evidence, partial results,
projection/checkpoint/version disclosure, reproducibility, and the absence of
fabricated evidence or canonical write-back.
