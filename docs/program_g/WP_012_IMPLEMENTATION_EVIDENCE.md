# WP-012 Policy and Approval Integration — Implementation Evidence

Status: Engineering complete; draft review pending
Work package: WP-012 — Policy and approval integration
Baseline: `5dca963c3067e31efecfba471cec5613358b31ac`
Branch: `feature/wp-012-policy-approval-integration`
Governing decisions: ADR-022, ADR-023; constrained by ADR-018, ADR-019,
ADR-020, and ADR-024

## Scope and Dependencies

WP-002 and WP-011 are closed and satisfy the catalog dependencies. This
increment adds a persistence-neutral orchestration boundary over existing
`TenantContext`, WP-011 Decision and Recommendation contracts, WP-010 evidence
packages, deterministic serialization, lineage/provenance, and explicit
authority concepts.

No existing runtime policy, approval, workflow, execution, connector, API, UI,
schema, migration, RLS, Supabase, or database behavior is changed.

## Implemented Contracts

- explicit versioned `PolicyReference` and deterministic `PolicyRule`;
- exact Decision version, evidence-package hash, policy version, normalized
  input, scope, evaluator version, and input-hash binding;
- exactly one `ALLOW`, `DENY`, or `INDETERMINATE` evaluation result;
- ordered reason evidence and fail-closed missing, stale, conflicting,
  superseded, unsupported, inactive, expired, revoked, cross-tenant, and
  incomplete handling;
- immutable governed evaluations and historical re-evaluation;
- exact-scope Approval with explicit requester, approver, effective time,
  expiry, state, lineage, and provenance;
- `ACTIVE`, `EXPIRED`, `REVOKED`, and `SUPERSEDED` Approval behavior;
- explicit requested and approved bounded Exception authority;
- `REQUESTED`, `ACTIVE`, `EXPIRED`, `REVOKED`, and `SUPERSEDED` Exception
  behavior;
- exception renewal as a new immutable version;
- requester/approver and Decision-proposer/authority segregation;
- absolute AI approval and AI exception-approval prohibition;
- tenant-bound lookup, mutation, authorization checking, and reconstruction;
- deterministic authorization-at-time reconstruction;
- no execution interface or execution side effect.

## Authority Boundary

The implementation preserves:

```text
Recommendation != Decision
Decision != Policy Authorization
Policy Authorization != Execution
```

An approved Decision is evaluation input. `ALLOW` is only eligible for
governed Approval. An active Approval or Exception is only a scoped policy
authorization result and never invokes execution.

`DENY` cannot produce Approval. A bounded, explicitly approved Exception may
apply to one identified failed policy rule. `INDETERMINATE` cannot be converted
into authorization by Approval or Exception.

## Acceptance Coverage

Focused tests cover:

- deterministic `ALLOW`, `DENY`, and `INDETERMINATE`;
- missing inputs and missing/unsupported policy versions;
- stale, missing, conflicting, and superseded evidence;
- invalid or superseded Decision state;
- inactive, expired, revoked, and superseded policy authority;
- policy-version change with preserved historical evaluation;
- exact Decision-version binding;
- authorized human Approval and exact-scope checks;
- expired, revoked, and superseded Approval denial;
- unauthorized, self, proposer, cross-tenant, and AI Approval denial;
- requested and active bounded Exception behavior;
- exception expiry, revocation, supersession, renewal, and immutable history;
- blocked exception scope expansion and cross-tenant access;
- AI exception-approval denial;
- `INDETERMINATE` exception bypass denial;
- deterministic complete authorization-at-time reconstruction;
- immutable contracts and absence of execution methods.

## Changed Files

- `policy_approval/__init__.py`
- `policy_approval/models.py`
- `policy_approval/service.py`
- `tests/policy_approval/test_policy_approval.py`
- `docs/program_g/WP_012_IMPLEMENTATION_EVIDENCE.md`

## Validation

| Gate | Result |
| --- | --- |
| WP-012 focused | 33 passed |
| Program G combined | 199 passed |
| P3 non-secret release gate | 94 passed |
| Full repository | 575 passed, 5 expected skips |
| Governance/security/certification | 68 passed |
| Secret-gated integrations | 5 collected, 5 expected no-secret skips |
| Contract/event governance CLI | Passed; 3 providers, 3 consumers |
| Connector certification CLI | Passed; 2 profiles, 4 pages, 4 observations |
| Ruff focused and repository critical checks | Passed |
| Compile/import | Passed; 1,154 active tracked Python files |
| `pip check` | Passed |
| `git diff --check` | Passed |
| Hosted CI | Pending draft PR |

The only local warnings were pre-existing Pydantic deprecations and the
workspace's non-writable pytest cache. They did not affect test behavior.

## Security and Compatibility

`TenantContext` is mandatory. All governed inputs and stored records use both
organization and tenant scope. Lookup failures do not disclose foreign
records. Policy and evidence ambiguity fail closed. Authority is exact-scope
and cannot be inferred from ownership, workflow state, Decision approval, or
AI output.

The implementation is additive and persistence-neutral. Existing services may
be adapted later only when they conform to ADR-022/023; this increment does not
replace them or alter runtime wiring.

## Migration, Database, and Rollback

Migration/schema required: **No**
Database touched: **No**

Rollback before merge is removal of the additive package, focused tests, and
this evidence record. No data rollback or external-system action is required.

## Remaining State

Engineering acceptance is fully covered locally. Draft PR publication,
exact-head hosted CI, Program G review, explicit merge approval, exact-main
post-merge validation, and closure remain pending. WP-013 has not started.
