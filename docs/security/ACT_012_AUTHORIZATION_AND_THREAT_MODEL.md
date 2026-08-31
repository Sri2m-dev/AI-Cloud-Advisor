# ACT-012 Authorization Matrix and Threat Model

## Production mutation authorization

Backend policy is authoritative. UI visibility and Streamlit session values are
not authorization decisions.

| Action | Allowed roles/authority | Backend authority | Audit/failure behavior |
| --- | --- | --- | --- |
| Upload evidence | Authenticated scoped prospect workflow | Admission and tenant scope | Rejection telemetry; no authority created |
| Confirm mapping | sales_engineer, finance, executive, client_admin, super_admin | `GovernancePolicy` | Durable governed audit when configured |
| Reject mapping | sales_engineer, finance, executive, client_admin, super_admin | `GovernancePolicy` | Reason required; durable audit |
| Override mapping | finance, client_admin, super_admin | `GovernancePolicy` | Mandatory durable audit; fail closed |
| Execute analysis | Current capability authorization matching scope, plan and normalization | Planner/executor | Block before result when stale/mismatched |
| Materialize canonical entity | super_admin, client_admin, operations | `EnterpriseRegistryService` plus observation scope | Cross-scope denial audited |
| Confirm/reject reconciliation | super_admin, client_admin, operations | `UniversalEvidenceSecurityPolicy` in reconciliation service | Mandatory durable audit; denial before target lookup/mutation |
| View governed audit | super_admin, client_admin, operations, auditor | `GovernedOperationsService` | Complete lifecycle scope required |
| Purge lifecycle scope | super_admin, client_admin, operations | `UniversalEvidenceSecurityPolicy` in lifecycle service | Request/completion audit; denial and audit before purge |
| Change activation | Explicit activation permission and administrative actor type | `PueActivationPolicy` | Mandatory durable audit |
| Enable/disable Kill Switch | Explicit Kill Switch permission and administrative actor type | `PueActivationPolicy` | Mandatory durable audit; fail closed |

Role strings are normalized through the existing `auth.role_constants` model.
No ACT-012-specific identity provider or parallel RBAC system is introduced.

Reconciliation and purge receive a bounded `WorkflowAuthorizationContext` whose
actor, active role, organization, tenant, prospect, and analysis are evaluated
together. Target scope is data to authorize, never authority. The production
wrappers do not expose legacy `actor_role` or `actor_id` escalation arguments.

Execution authority is capability/fingerprint based (`SYSTEM_INTERNAL`), rather
than role-string based. Mapping, activation/Kill Switch, and audit querying expose
trusted-context entry points that construct their established internal actors and
queries server-side. The actor-based mutation methods and raw `AuditQuery` remain
`LEGACY_INTERNAL_ONLY`; production composition must use the authorized entry points.

## Final privileged-boundary inventory

| Boundary | Classification |
| --- | --- |
| Upload Evidence | TRUSTED_CONTEXT / admission scope |
| Confirm, Reject, Override Mapping | TRUSTED_CONTEXT |
| Authorize Analysis | SYSTEM_INTERNAL capability authority |
| Confirm, Reject Match | TRUSTED_CONTEXT |
| Purge | TRUSTED_CONTEXT |
| Activation Change | TRUSTED_CONTEXT |
| Kill Switch Enable/Disable | TRUSTED_CONTEXT |
| Audit Query | TRUSTED_CONTEXT |

The underlying actor APIs are retained for certified service-owned workflows and
older tests, not as client authority. No production wrapper added by ACT-012
accepts caller-defined role, permission, tenant, prospect, or analysis authority.

## Threat model

Assets are uploaded evidence, governed mappings, execution authorizations,
plans/results, canonical entities and relationships, reconciliation decisions and
bindings, audit history, tenant scope, and credentials.

Actors include authorized and unauthorized client users, cross-tenant users,
malicious evidence producers, prompt attackers, service identities, and operators.
Trust boundaries are the UI/session, authenticated service context, Universal
Evidence services, lifecycle persistence, canonical registries, file admission,
and Ask interpretation/execution.

Primary threats and controls:

- Spoofing and privilege escalation: backend role/permission policies; session
  hiding is never authority.
- Cross-tenant disclosure and IDOR: complete scope is required by repositories;
  canonical objects are revalidated against registry tenant context.
- Tampering: append-only audit, immutable decision identity, target type/scope
  validation, and audit-before-sensitive-mutation.
- Replay and staleness: evidence, governance, normalization, authorization, plan,
  and result fingerprints must remain current and scope-compatible.
- Prompt/evidence injection: input is data, never policy; injection-like questions
  are blocked without persisting the prompt body.
- Financial authority forgery: headers, filenames, locale, workbook totals, prompt
  text, and session values cannot create governed currency.
- Availability/failure: persistence and required-audit failures are fail-closed;
  optional telemetry failure does not corrupt authority.
- Concurrency and partial writes: reconciliation decisions are serialized and
  singular; durable decisions/bindings are written before becoming in-memory
  authority; binding retry is idempotent. Measurement re-resolves activation
  after planning so a newly enabled Kill Switch blocks execution.
- Information disclosure: safe error classes and `NX-...` support references avoid
  raw evidence, credentials, paths, SQL, tracebacks, and foreign target IDs.

## File and formula posture

Upload filenames are treated as metadata and are not joined to filesystem paths by
Universal Evidence admission. XLSX files are opened by `openpyxl` with macros not
executed; formulas are read as workbook cell content and are never evaluated by
Python, a shell, or a spreadsheet application. CSV content is parsed with the
standard library and is never passed to `eval`, `exec`, or a command processor.

## Residual deployment responsibilities

Database row-level security, encryption-key provisioning, request-size limits,
rate limiting, and retention scheduling remain deployment controls. ACT-012 tests
certify application fail-closed behavior and do not substitute for infrastructure
configuration review.

Streamlit session role values are `UX_SELECTION`/`CACHED_CONTEXT`, not a certified
privileged service authority. Production composition creates the trusted tenant
context from the authenticated principal; domain mutation adapters derive their
actors from that context.
