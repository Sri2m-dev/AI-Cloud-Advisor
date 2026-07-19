# WP-002 — Tenant Identity and Authorization Foundation

Status: Implemented; pending Program G review

Baseline: `main` at `0f038fda7b695a4b035db9a2b957c6cc1229c22b`

Released baseline: `v1.2.0-data-fabric`

Branch: `feature/wp-002-tenant-identity-authorization`

Delivery owner: Srikanth Mudaliar

Increment: Increment 1

## Outcome

WP-002 introduces one immutable, deny-by-default tenant authorization envelope for application boundaries. It normalizes principal identity, preserves separate organization and tenant partitions, carries roles and permissions, produces tenant-partitioned cache keys, validates scoped payloads, and rejects untrusted service contexts.

FastAPI's existing `tenant_guard` now delegates tenant validation to the shared envelope without changing its return type or positive-path API behavior. Reusable adapters cover Streamlit, connectors, caches, background jobs, event consumers, and AI services. Those adapters establish guarded entry points; they do not add capabilities to those boundaries.

## Core rules

- Missing organization, tenant, subject, subject type, or source boundary is denied.
- Organization and tenant mismatches are distinct, explicit failures.
- Requested permissions must be present in the verified context.
- Cache keys always include namespace, organization, tenant, and item key.
- Jobs, events, and AI require a trusted service subject and exact source boundary.
- Scoped payloads must carry matching organization and tenant identifiers.
- No connector fallback identifier is accepted by the guarded connector adapter.

## Scope boundary

No Data Fabric contract, registry, identity-resolution algorithm, connector capability, AI capability, UI, schema, migration, RLS, Supabase configuration, or later work-package feature changed.

## Usage pattern

Create context only from an authenticated principal or trusted service identity:

```python
context = TenantAuthorizationContext.from_principal(
    principal,
    source_boundary="api",
)
context.authorize(
    organization_id=requested_organization,
    tenant_id=requested_tenant,
    permission="resource:read",
)
```

Service boundaries use the matching adapter (`authorize_job`, `authorize_event`, or `authorize_ai`) and cannot substitute a user context or a context created for another boundary.

## Acceptance criteria

- Shared identity context is immutable and deny-by-default.
- FastAPI rejects missing and mismatched tenant identity.
- Streamlit and connector adapters reject cross-organization access.
- Cache access creates tenant-partitioned keys and rejects unscoped keys.
- Jobs and events reject untrusted or cross-tenant payloads.
- AI access rejects untrusted or cross-organization context.
- Existing positive paths and public APIs remain compatible.
- WP-001 compatibility, full repository, and P3 gates remain green.
- Hosted CI succeeds before Program G merge review.

## Governance boundary

This foundation does not authorize wholesale migration of every application caller. Future work packages must adopt the guarded entry points when modifying their owned boundaries. Bypassing the envelope in new tenant-aware code is an architecture-conformance failure.
