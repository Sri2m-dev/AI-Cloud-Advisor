# Gate 1 — Preservation and Rollback Plan

Target: `nexora-p3-validation-restoration`
(`uuqprdnqhbsmwubeqouw`)
Status: **No cloud modifications authorized or performed.**

## Local implementation update

The revised migration touches only new application-owned namespaces
`nexora_identity` and `nexora_customer_workflow`, plus a narrow grant of
schema USAGE and `hmac(bytea, bytea, text)` EXECUTE to the V1 owner on the
existing `pgcrypto` schema. It contains no statements against `auth`,
`data_fabric`, `supabase_migrations`, `public.users`, or Supabase-managed
roles. The disposable PG17 preservation test compares roles/memberships,
Auth sentinel data, G07 sentinel data, the existing migration record,
existing public objects and application identity mappings before and after
the restore; it also confirms `public.users` remains absent in that target.

The identity-mapping rows are included in the encrypted V2 logical package
and compared exactly with the target. They are **not** inserted by the
runtime restore credential. Any future target mapping provisioning requires
a separate owner-only authorization and a matching pre/post preservation
snapshot; the workflow restore then runs under the least-privilege runtime
role. This preserves the rule that runtime users cannot grant themselves
membership.

This local test does not provide the required live pre-change snapshot or
prove that Supabase accepts the narrow extension-schema grant. Therefore it
does not authorize a migration or cloud restore. See
[LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md](./LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md).

## Non-negotiable preservation boundary

Future V1 DDL, if separately authorized, must be confined to new,
application-owned identity and `nexora_customer_workflow` objects. It must
not alter, rename, delete, re-own, grant/revoke on, migrate, or restore over:

- Any of the ten historical `data_fabric` G07 tables, functions, triggers,
  constraints, indexes, policies, ownership, ACLs, role memberships or data.
- Any Supabase-managed `auth` schema object, user, identity, token/session,
  provider configuration, key, trigger, function, grant or ownership.
- Existing `supabase_migrations` records, including
  `20260904042847_enforce_relationship_timestamp_order`.
- Existing installed extensions or their schemas/owners.
- Any existing role, membership, database/schema/table/function privilege,
  public object, application data or unrelated tenant.

The supplied live findings establish Auth, ten G07 tables, G07 RLS enabled
without FORCE and zero policies, one existing migration, and installed
`pgcrypto` in `extensions`. They do not enumerate the full G07 functions,
grants, dependencies, exact extension overload, other public objects,
organization relation, existing role memberships, or row fingerprints.
Those are required baseline evidence, not assumed empty.

## Pre-change / post-change proof package

Use the exact same read-only snapshot query set, database identity and
normalized output format before and after. Restrict results and store them
outside the target in approved access-controlled evidence storage. Include
snapshot UTC time, project ref, server major/minor, query bundle hash and
result bundle SHA-256.

| Snapshot domain | Capture and compare | What it proves / limitation |
|---|---|---|
| Schemas/relations | Schema names/owners/ACLs; relation names/kinds/owners/ACLs; RLS and FORCE flags; columns/types/nullability; constraints/validation; indexes/definitions/validity. Include all existing `data_fabric`, `auth`, `public`, migration and extension namespaces. | Detects catalog object changes; does not prove row values unchanged. |
| Functions/triggers | Function identity args/result/language/owner/security-definer/volatility/fixed search path/ACL and SHA-256 of canonical `pg_get_functiondef`; trigger definition, enabled/internal flags, table binding. | Detects changed function/trigger definitions and grants. Keep function bodies in restricted output or hash only. |
| Policies/grants | `pg_policies` USING/WITH CHECK/roles/cmd/permissive; relation/schema/database/function/default ACLs and role memberships/options. | Proves permission metadata unchanged; no secret/password verifier fields. |
| Roles/extensions | Role attributes excluding passwords; role membership; extension name/version/schema/owner. | Detects managed-role and extension changes; do not infer ability to grant from role name. |
| Migration ledger | Exact version/name/hash for existing rows before and after. | Proves the existing G07/history record is unchanged; do not add records during this assessment. |
| G07 data | Restricted per-table exact counts plus deterministic SHA-256 of canonical row serialization, captured read-only before/after for each of the ten tables. | Required to prove historical row content unchanged; catalog-only metadata is insufficient. Fingerprints are not to be published with row contents. |
| Auth preservation | Catalog/function/grant snapshot and provider-supported non-secret metadata. No user-row/token export. | Proves managed Auth catalog/configuration unchanged within snapshot coverage; does not assert Auth availability or identity equivalence. |
| New V1 target | Before: confirm all proposed names absent or exactly approved. After: exact object/owner/ACL/RLS/function/trigger hash and empty workflow table checks. | Demonstrates additive scope only. Any unexpected pre-existing object stops the migration. |

The ten table names and their row fingerprints must be obtained through the
authorized read-only evidence process; the supplied summary alone cannot be
used to fabricate a comparison.

## Execution guard and rollback decision tree

1. **Before DDL:** verify every prerequisite in
   [AUTHORIZATION_CHECKLIST.md](./AUTHORIZATION_CHECKLIST.md), stage signed
   migration hash and exact target ref, and capture the complete baseline.
   If any protected snapshot is unavailable, stop.
2. **During DDL:** use only the separately reviewed versioned migration,
   approved migration principal and an explicit transaction where supported.
   Do not run `scripts/provision_customer_workflow_postgres.py` unchanged: it
   also writes JWT settings and creates/alters an application login.
3. **Failure before commit:** capture sanitized diagnostics, verify the
   database transaction rolled back and compare the after-state against the
   baseline. Do not automatically retry.
4. **Failure after partial/provider commit:** freeze the target; preserve
   catalog and sanitized logs; no cleanup, compensating DDL, role change,
   schema drop, data delete or rerun without a new exact owner authorization.
5. **Successful commit:** verify all V1 assertions read-only, protected
   snapshot equality, and empty workflow data. A migration commit is not a
   restore authorization.
6. **Future restore:** separately authorize synthetic PG17 logical restore
   only after the migrated contract and revised recovery tool pass. The
   restore must not write Auth or G07 objects and must refuse a non-empty
   target.

## Rollback limitations

- DDL changes within one successful PostgreSQL transaction can be rolled
  back before commit; a later commit requires a separately reviewed forward
  repair or new migration.
- Supabase provider operations, migration-ledger writes, secret provisioning,
  role/password changes, external application deployments and audit events
  may not share the database transaction.
- `DROP SCHEMA ... CASCADE`, project reset, role deletion, policy-wide
  replacement, restoring the PG18 full package, or deleting any G07/Auth
  object is not an allowed rollback.
- If identity mapping rows or workflow data have been committed, deletion is
  not an automatic rollback. Preserve evidence and obtain explicit data-owner
  direction.
- No cleanup of historical project, storage, Auth records or G07 evidence is
  authorized by this plan.

No cloud snapshot, write, migration, restore or rollback was performed for
this assessment.
