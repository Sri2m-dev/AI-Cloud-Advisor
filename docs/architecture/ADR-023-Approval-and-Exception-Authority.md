# ADR-023: Approval and Exception Authority

Status: Accepted
Date: 2026-07-24
Program: Program G — WP-012
Decision authority: Srikanth Mudaliar, Owner, Chief Architect, Program Sponsor

## Context

An approved Decision and an `ALLOW` policy evaluation do not themselves grant
authority. Nexora requires explicit, tenant-bound approval and exception
records with validated actors, exact scope, temporal validity, immutable
history, and segregation of duties.

## Decision

Adopt persistence-neutral governed Approval and Exception contracts. Authority
is explicit and must never be inferred from Recommendation existence, Decision
approval, an `ALLOW` evaluation, workflow progression, ownership, or AI output.

Only an `ACTIVE` authority record that matches the exact tenant, Decision,
evaluation, scope, and evaluation time can satisfy an authorization
requirement. Even valid policy authorization is not execution:

```text
ACTIVE APPROVAL != EXECUTION
ACTIVE EXCEPTION != EXECUTION
```

## Approval Contract

Every Approval identifies:

- approval identity and version;
- tenant and organization;
- exact Decision identity and version;
- exact policy evaluation identity and result;
- approving actor and actor type;
- explicit authority scope;
- issued and effective timestamps;
- optional expiry timestamp;
- lifecycle status;
- lineage, provenance, and audit history.

Approval lifecycle states are:

- `ACTIVE`;
- `EXPIRED`;
- `REVOKED`;
- `SUPERSEDED`.

Only `ACTIVE` satisfies approval. Expired, revoked, and superseded approvals
fail closed. Renewal or replacement creates a governed new version or record;
it does not rewrite history.

## Authority and Segregation of Duties

Approval validates explicit approver authority for the tenant, policy,
Decision, and requested scope. Creating, proposing, reviewing, or owning a
Recommendation or Decision grants no approval authority.

Where segregation applies:

- the Decision proposer and Decision approver differ; and/or
- the policy-approval requester and policy approver differ.

A failed authority or segregation check creates no active Approval.

## AI Boundary

AI may recommend approval, explain eligibility, request approval, and request
an exception.

AI must not grant approval, approve its own or another AI request, issue or
extend an exception, revoke controls to enable itself, or fabricate authority.
An authorized human or separately governed non-AI authority is required.

## Exception Contract

An Exception is explicit, bounded authority to except one identified policy
rule. It is narrower than unrestricted authorization and identifies:

- exception identity and version;
- tenant and organization;
- requesting and approving actors and actor types;
- exact policy and rule;
- Decision and policy-evaluation references;
- justification and governed evidence;
- exact scope;
- effective and expiry timestamps;
- lifecycle status;
- lineage, provenance, and immutable audit history.

Exceptions are bounded, auditable, revocable, and non-transferable across
tenants. They are time-limited where applicable; no permanent implicit
exception exists.

Exception lifecycle states are:

- `REQUESTED`;
- `ACTIVE`;
- `EXPIRED`;
- `REVOKED`;
- `SUPERSEDED`.

Only `ACTIVE`, in-scope, temporally valid authority may apply. Renewal creates a
governed new version and history event. Revocation and supersession preserve
prior state. Scope expansion requires new authority and may not mutate an
existing Exception.

## Tenant and Scope Boundary

`TenantContext` is mandatory for creating, evaluating, looking up, changing,
and reconstructing Approval and Exception authority. Actors, Decision,
evaluation, policy, evidence, and authority records must share the context's
tenant and organization.

Authority matches an exact requested scope. A broader, different, expired,
revoked, superseded, or cross-tenant request fails closed.

## Reconstruction

Authorization history deterministically reconstructs:

```text
Decision and version
  -> Evidence package
  -> Policy and version
  -> Evaluation result and reasons
  -> Approval or Exception
  -> Authority actor
  -> Scope
  -> Effective and expiry time
  -> Current and historical state
  -> Lineage and provenance
```

Historical evaluations, approvals, exceptions, and lifecycle events are
immutable. Reconstruction answers why an action was or was not authorized at a
specified time without substituting current state for historical state.

## Compatibility and Reuse

WP-012 reuses existing approval services, authority concepts, `TenantContext`,
WP-011 Decisions, WP-010 evidence, WP-009 explanations, and Data Fabric
lineage/provenance/versioning through bounded adapters where they conform.

This decision selects no database, schema, public API, UI, connector, execution
workflow, or competing approval framework.

## Consequences

Approvals and exceptions become explicit scoped authority with deterministic
expiry, revocation, supersession, segregation, and audit behavior. WP-013 and
later execution controls must consume exact governed authorization rather than
infer it.

## Implementation Acceptance

Evidence must cover authorized human approval; unauthorized, segregated,
cross-tenant, and all AI approval rejection; exact-scope matching; active,
expired, revoked, and superseded approvals; requested, active, expired,
revoked, renewed, and superseded exceptions; blocked scope expansion;
immutable lifecycle history; deterministic historical reconstruction; and no
execution side effect.
