# ADR-020: Recommendation and Decision Authority

Status: Accepted
Date: 2026-07-24
Program: Program G — WP-011
Decision authority: Srikanth Mudaliar, Owner, Chief Architect, Program Sponsor

## Context

Nexora can derive findings, alternatives, and explainable evidence, but a
generated recommendation must never become authorization merely because it was
produced by AI or a trusted service. The platform requires a governed boundary
between proposals, human or governed dispositions, later policy authorization,
and execution.

## Decision

Adopt separate, tenant-bound Recommendation and Decision contracts with
immutable version and event history.

A **Recommendation** is a governed proposal. It identifies:

- finding or problem;
- proposed action and expected outcome;
- explicit alternatives, including “no action” when appropriate;
- supporting and contradicting evidence;
- assumptions and risks;
- supported confidence;
- lineage and provenance;
- proposer identity and proposer type.

A Recommendation is not authorization to execute.

A **Decision** is an authorized human or governed disposition of one specific
Recommendation version. Its disposition is:

- `APPROVE`;
- `REJECT`; or
- `REQUEST_REVISION`.

Recommendation history may also terminate as `WITHDRAWN` or `SUPERSEDED`.

## Authority and Segregation

- `TenantContext` is mandatory for all Recommendation and Decision operations.
- Authorization is evaluated before a Decision is created.
- The approver must possess explicit Decision authority in the requesting
  tenant.
- Where segregation is required, `proposer_actor_id` must differ from
  `approver_actor_id`.
- Cross-tenant access, evidence use, approval, reconstruction, correction, and
  supersession fail closed.
- Authorization failure creates no Decision.

## AI Boundary

AI may identify findings, propose actions and alternatives, summarize governed
evidence, estimate impacts, explain reasoning, and request more evidence.

AI must not:

- approve any Recommendation;
- act as final Decision authority;
- fabricate or impersonate human approval;
- convert its proposal into an approved Decision;
- bypass policy or approval controls;
- execute merely because it generated a Recommendation.

AI-generated Recommendations are explicitly marked with proposer type `AI`.
All AI approver identities are rejected, including identities different from
the AI proposer. Authorized human or separately governed non-AI authority is
required.

## Evidence

WP-011 binds Recommendation versions to WP-010 governed evidence packages; it
does not create another evidence framework.

Decision evaluation distinguishes evidence that is:

- `AVAILABLE`;
- `STALE`;
- `MISSING`;
- `CONFLICTING`;
- `SUPERSEDED`.

Evidence is never fabricated. Superseded evidence cannot silently support a new
approval. Missing, stale, conflicting, or otherwise insufficient evidence
causes deterministic rejection or `REQUEST_REVISION`; it never silently
produces approval.

## Lifecycle

The minimum Recommendation lifecycle is:

```text
DRAFT -> PROPOSED -> UNDER_REVIEW
UNDER_REVIEW -> APPROVED | REJECTED | REVISION_REQUIRED
DRAFT | PROPOSED | UNDER_REVIEW -> WITHDRAWN
APPROVED | REJECTED | REVISION_REQUIRED -> SUPERSEDED
```

Submitting for review requires a complete Recommendation and governed evidence
binding. Decision creation performs the terminal transition. Invalid
transitions fail closed. State is changed only through the lifecycle service,
and every transition appends a governed history event.

## Correction and Supersession

- Recommendation and Decision records are immutable.
- Approved or rejected Decisions are never rewritten.
- A correction creates a new Recommendation version and history event.
- A superseding Recommendation preserves the original Recommendation,
  Decision, evidence references, actors, timestamps, and version history.
- Supersession identifies both predecessor and successor.
- A new Decision applies only to the exact Recommendation version reviewed.

## Reconstruction

A deterministic Decision reconstruction identifies:

- Recommendation ID and version;
- finding, action, expected outcome, alternatives, assumptions, and risks;
- evidence package identity and integrity hash;
- supporting and contradicting evidence roles;
- proposer identity and type;
- reviewer and approver;
- authority evaluation and disposition;
- Recommendation and Decision timestamps and states;
- lineage and provenance references;
- correction and supersession history.

Reconstruction distinguishes retained facts and evidence from derived or AI
reasoning. Stable ordering and deterministic serialization apply.

## WP-011, WP-012, and Execution Boundary

```text
Recommendation != Decision
Decision != Policy Authorization
Policy Authorization != Execution
```

WP-011 governs Recommendation and Decision only. WP-012 owns policy and
approval integration. Later packages own execution and outcomes. No WP-011
component authorizes or performs execution.

## Compatibility and Reuse

The implementation reuses `TenantContext`, WP-009 governed query/explainability
outputs, WP-010 evidence packages, P3 lineage/provenance/versioning, ADR-024
registry boundaries, and existing recommendation, approval, and governance
services through adapters where safe.

This decision does not select persistence, create a schema, change existing
runtime services, expose a public API, or authorize AI execution.

## Acceptance

Implementation evidence must cover human and AI proposals, alternatives,
evidence binding and insufficiency states, valid approval/rejection/revision,
withdrawal, correction, supersession, proposer/approver segregation, all AI
approval rejection, unauthorized and cross-tenant rejection, invalid
transitions, immutable history, deterministic complete reconstruction, and no
execution side effect.
