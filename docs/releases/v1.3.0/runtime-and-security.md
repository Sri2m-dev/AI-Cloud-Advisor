# Runtime Composition, RBAC, Browser, and Security Baseline

## Persona and RBAC matrix

| Persona | Canonical role | Certified landing page | Baseline authority |
| --- | --- | --- | --- |
| Administrator | `super_admin` | Executive Dashboard | Platform and governed lifecycle administration |
| CEO | `executive` | Executive Dashboard | Read/decision posture; no implicit mutation authority |
| CIO | `cio` | Technology Portfolio Overview | Technology and governance review |
| CTO alias | `cio` | Technology Portfolio Overview | Alias normalized to CIO authority |
| Finance | `finance` | FinOps Dashboard | Financial review and permitted registry/mapping work |
| Auditor | `auditor` | Audit Timeline | Read-only evidence and history |
| Operations | `operations` | Operations Workspace | Operational review and permitted technical mapping work |

Server-side `require_role` checks enforce direct-route access. Sidebar visibility is not
treated as authorization. Tenant context carries the authenticated organization and
authorized organization set through service and repository calls.

## Runtime repository composition

| Domain | Composition | Development fallback | Production behavior |
| --- | --- | --- | --- |
| Cloud Account Registry | `cloud_account_registry_composition` | SQLite/local repository | Tenant-scoped Supabase |
| Enterprise Spend | `enterprise_spend_composition` | Local/empty safe repository | Tenant-scoped Supabase |
| Audit | `audit_composition` | SQLite audit repository | Valid configured backend required |
| Leadership | `leadership_composition` | SQLite repository | Invalid configuration fails closed |
| Finance | `technology_spend_composition` | SQLite repository | Invalid configuration fails closed |
| Operations | `operations_workspace_composition` | SQLite repository | Invalid configuration fails closed |

Missing, placeholder, or invalid non-production Supabase settings select safe local
repositories. Optional missing or unscoped local marts produce empty results. Production
never enables local authentication or silently falls back from invalid persistence
configuration.

## Browser certification

Acceptance-owner browser certification passed for Administrator, CEO, CIO, CTO alias,
Finance, Auditor, and Operations. Each persona passed login, displayed identity/role/org,
landing-page routing, sidebar navigation, direct-route RBAC, logout, and no-traceback
checks. This certifies runtime behavior, not real DEV financial values from SQLite.

## Security status

- Production authentication remains Supabase-backed and fail closed.
- Non-production local passwords use salted PBKDF2-SHA256 hashes; credentials are not
  written to audit records.
- Tenant identifiers are mandatory at repository boundaries covered by the release.
- Supabase repositories use explicit tenant filters and existing RLS/constraint controls.
- Local repositories refuse unscoped tables rather than returning cross-tenant data.
- Resolution/classification changes preserve explicit reason, evidence, version, audit,
  lifecycle, stale-state, duplicate, and rollback protections.
- CI, P3 safety tests, governance checks, persona direct-route tests, Ruff, compile/import,
  and dependency checks passed on the release commit.
- No production mutation, CUR file #2 ingestion, hardcoded bypass, or release-secret
  disclosure occurred during baseline certification.

No new penetration test or independent external security assessment was performed for
P4.3.0; this status records the automated and manually certified controls of v1.3.0.
