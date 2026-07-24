# ADR-022: Policy Evaluation and Authorization

Status: Accepted
Date: 2026-07-24
Program: Program G — WP-012
Decision authority: Srikanth Mudaliar, Owner, Chief Architect, Program Sponsor

## Context

WP-011 established governed Recommendation and Decision contracts. An approved
Decision is necessary input to later authorization, but it is not permission to
execute. Nexora requires deterministic, tenant-bound policy evaluation before
approval authority can be considered.

The authority chain is invariant:

```text
Recommendation != Decision
Decision != Policy Authorization
Policy Authorization != Execution
```

## Decision

Adopt a persistence-neutral policy-evaluation contract that binds an exact
Decision version, governed evidence references, an exact policy version, and an
explicit evaluation context.

Every evaluation produces exactly one governed result:

- `ALLOW`: policy requirements are satisfied and the request is eligible to
  continue to separate approval and authorization controls;
- `DENY`: policy requirements are not satisfied and authorization is
  prohibited;
- `INDETERMINATE`: required evaluation inputs or a deterministic conclusion are
  unavailable and authorization is prohibited.

Neither `ALLOW` nor an approved Decision is execution authority.

## Fail-Closed Evaluation

Evaluation must not fall back to `ALLOW`. Applicable failures produce
`INDETERMINATE` or `DENY` according to explicit policy semantics and block
authorization. These include:

- missing policy or unsupported policy version;
- missing mandatory input or evidence;
- stale evidence when freshness is mandatory;
- unresolved conflicting evidence;
- superseded evidence;
- invalid or superseded Decision;
- expired, revoked, or superseded authority;
- cross-tenant Decision, evidence, policy, lookup, or reconstruction;
- policy evaluator failure.

The result and reason code are explicit. Silent filtering must not remove an
unsafe input and produce a misleading `ALLOW`.

## Determinism and Reconstruction

Equivalent Decision content and version, evidence state, policy identity and
version, and normalized evaluation context produce an equivalent result and
ordered reason set.

Each governed evaluation records or references:

- tenant and organization scope;
- Decision identity and version;
- policy identity and version;
- evidence references and their evaluated state;
- normalized input state and constraints;
- evaluation timestamp;
- result and ordered reasons;
- lineage and provenance references;
- evaluator contract version and deterministic input hash.

Historical evaluations are immutable. A policy or Decision version change
requires a new evaluation and never rewrites an earlier result.

## Policy Contract and Versioning

A policy reference identifies:

- policy identity;
- tenant scope;
- version;
- effective and optional expiry times;
- supported evaluator contract version;
- deterministic rules and required inputs;
- evidence and freshness requirements;
- lineage and provenance.

An evaluation applies only the referenced version. Unsupported, inactive,
expired, revoked, or superseded policy authority fails closed.

## Tenant Boundary

`TenantContext` is mandatory for evaluation, authorization lookup, and
reconstruction. The Decision, policy, evidence, evaluation, and requesting
context must share the same tenant and organization. Cross-tenant input is
rejected before a result can be used for authorization.

## AI Boundary

AI may assist evaluation, explain results, identify missing evidence, recommend
remediation, and propose an exception request.

AI must not alter policy to obtain `ALLOW`, convert `INDETERMINATE` into
`ALLOW`, grant authorization, approve an exception, extend approval validity,
remove human controls, or self-authorize execution. Deterministic policy
authority remains outside AI discretion.

## Explainability and Evidence

Every result explains why it is `ALLOW`, `DENY`, or `INDETERMINATE`. Governed
facts and evidence remain distinguishable from derived reasoning. ADR-018
governed-query determinism and ADR-019 evidence disclosure, freshness,
partial-result, and no-fabrication requirements apply.

## Compatibility and Reuse

WP-012 reuses `TenantContext`, the WP-011 Decision package, WP-010 evidence
packages, WP-009 explainability, Data Fabric lineage/provenance/versioning, and
existing policy services through bounded adapters where they conform.

This decision creates no database schema, persistence selection, public API,
workflow execution, or competing policy framework.

## Consequences

Policy authorization becomes explicit, deterministic, explainable, and
reconstructable. Missing or ambiguous state blocks rather than silently
authorizes. Approval and exception authority remain governed separately by
ADR-023, and execution remains outside WP-012.

## Implementation Acceptance

Evidence must cover all three results; fail-closed missing, stale, conflicting,
superseded, unsupported, failed, and cross-tenant inputs; exact Decision,
evidence, and policy version binding; deterministic reasons and reconstruction;
historical preservation across re-evaluation; AI authority prohibitions; and
absence of execution side effects.
