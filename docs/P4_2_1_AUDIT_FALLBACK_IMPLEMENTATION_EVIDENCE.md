# P4.2.1 Local Audit Fallback Implementation Evidence

Branch: `feature/p4-2-enterprise-classification-engine`

## Root cause and remediation

`services.audit_service` previously called the lazy global Supabase client for every
central audit read and write. In supported local mode the missing URL therefore raised
before an event could be recorded, and the service printed a full traceback repeatedly.

The central service now composes an `AuditRepository` at runtime:

- a valid HTTPS Supabase URL plus a non-placeholder key selects the existing
  `public.audit_events` event shape through `SupabaseAuditRepository`;
- missing or placeholder configuration in a non-production environment selects the
  append-only, tenant-scoped `SQLiteAuditRepository`;
- production without valid Supabase configuration fails closed and never selects
  SQLite.

The local table is `local_audit_events`. It retains actor, event/action identity,
resource identity, event details (including before/after state, reason, role and other
metadata), timestamp, and exact organization scope. Update and delete triggers enforce
append-only behavior. Ordering is deterministic by timestamp and event ID. This is an
additive runtime SQLite schema; no Supabase migration or production schema changed.

`services.audit_timeline_service` reads current events through the corrected central
service. Historical Supabase legacy tables remain read-only fallbacks only when the
Supabase repository is active.

## Scope and bypass review

The active central audit callers (authentication, reports, alerts, workflows and
enterprise intelligence) now inherit repository composition without source changes.
Cloud Account Registry and FG-002 resolution deliberately retain their governed,
tenant-scoped `cloud_account_registry_audit` repository/RPC transaction rather than
duplicating those events into a second stream. Classification result persistence and
approved-value protection remain versioned in the existing classification repository;
no direct classification audit-table write bypass was found. Approval workflow and
operations workspace own separate domain audit projections and are outside this central
event-stream remediation.

## Certification record

Local certification on 2026-08-09 produced:

- audit fallback: 7 passed;
- AUTH001 / FG-001 / FG-002 / P4.2: 55 passed;
- PVT-003A/B/C: 60 passed, 2 environment skips;
- P3 gate: 94 passed;
- governance/certification: 40 passed plus both repository scripts passed;
- full repository suite: 768 passed, 7 expected skips;
- Ruff, compile/import, `pip check`, and `git diff --check`: passed;
- local health endpoint: HTTP 200 / `ok` with Supabase variables absent;
- SQLite runtime event: persisted and read back in the same organization scope;
- runtime logs: no `AUDIT INSERT FAILED`, missing-Supabase `RuntimeError`, or traceback.

Interactive page certification remains pending because the required in-app browser
connection was unavailable in the execution environment. This evidence does not replace
that browser gate or authorize merge. Hosted CI run `31311889510` passed on remediation
commit `31eff4114cb9a39c30068f2822bdb9e9a3788eb0`; the final documentation descendant
must also pass the same PR gate before handoff.
