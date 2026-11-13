# Gate 1 — Exact V1 Migration Delta

Assessment timestamp: 2026-11-13 11:51:20 +05:30
Target: `nexora-p3-validation-restoration`
(`uuqprdnqhbsmwubeqouw`), `ap-southeast-2`, PostgreSQL 17.11
Mode: review of owner-supplied read-only catalog findings and local source;
no cloud query or write was performed by this assessment.

## Finding provenance and decision

The target facts below are the independently confirmed read-only results
provided for this assessment. They are point-in-time findings, not permission
to modify the project. Local object requirements were checked against
[`001_customer_workflow_postgres.sql`](../../../database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql),
[`provision_customer_workflow_postgres.py`](../../../scripts/provision_customer_workflow_postgres.py),
[`postgres_v1_workflow_recovery.py`](../../../scripts/postgres_v1_workflow_recovery.py),
[`postgres_customer_workflow_repository.py`](../../../services/postgres_customer_workflow_repository.py),
and [`test_customer_workflow_postgres.py`](../../../tests/customer_workflow/test_customer_workflow_postgres.py).

**Decision:** the unmodified canonical migration cannot be applied to the
reported target: its first `DO` block raises if `public.users` is absent.
The workflow schema, workflow tables, and owner/runtime group roles are also
reported absent. The migration additionally modifies policies/grants on
`public.users`, creates `pgcrypto` with `public` as the requested extension
schema, and calls `public.hmac`; the target has `pgcrypto` installed under
`extensions`. The existence and execute privilege of the exact `hmac`
function signature in `public` are not established. Do not run this migration
unchanged or change extension placement to work around that mismatch.

**Implementation amendment:** the local canonical contract has now been
revised. The legacy `public.users` findings below remain accurate for the
fixed project's reported point-in-time catalog, but `public.users` is no
longer a required V1 object. The locally qualified identity object is
`nexora_identity.memberships`; `pgcrypto` is checked in place and the
`hmac(bytea, bytea, text)` function is resolved from the installed extension
schema. The migration grants only schema USAGE and function EXECUTE on that
symbol to the non-login V1 owner role. These are local design results only;
actual Supabase role capability and extension-schema grant compatibility
remain **UNVERIFIED**. See
[LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md](./LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md)
for the exact current contract and test evidence.

## Object-by-object comparison

Statuses refer to the reported live catalog at the assessment timestamp.
“Missing” is only assigned where the supplied findings establish absence.
An expected but not individually enumerated sub-object is marked
**UNVERIFIED** rather than inferred absent.

| Object / requirement | Canonical contract | Target status | Evidence / next read-only check |
|---|---|---|---|
| PostgreSQL version | Workflow restore requires major 17 | **PRESENT** | Reported target is PostgreSQL 17.11. |
| `pgcrypto` extension | Required for HMAC JWT signature check | **PRESENT, placement incompatible pending symbol check** | Reported installed in `extensions`; canonical SQL invokes `public.hmac(bytea, bytea, text)`. Check `pg_extension.extnamespace`, `pg_proc` schema/name/identity args, and `has_function_privilege` for proposed roles. |
| `nexora_customer_workflow` schema | Owner `nxr_customer_workflow_owner` | **MISSING** | Explicitly reported absent. |
| `jwt_verification_settings` | `singleton boolean` PK, default `true`, check `singleton`; `signing_secret text NOT NULL`; `issuer text NOT NULL` | **MISSING** | Parent schema reported absent. It must not be populated with a Supabase managed secret unless the supported key/algorithm and custody contract is approved. |
| `events` columns | Ordered columns: `event_id text`, `event_type text`, `organization_id text`, `tenant_id text`, `workspace_id text`, `actor_id text`, `idempotency_key text`, `payload_fingerprint text`, `payload_ciphertext text`, `occurred_at timestamptz`, `approval_id text`, `approval_action text`, `approval_state text`, `approval_stage text`, `approval_version integer`, `approval_requesting_actor text`, `approval_escalated_to text`, `ask_event_id text`, `decision_event_id text`, `evidence_event_id text` | **MISSING** | Parent schema reported absent. |
| `events` constraints | PK `event_id`; event-type and tenant-equals-organization checks; unique tenant idempotency and composite event-scope keys; conditional approval-id check; three composite self-FKs for Ask/decision/evidence | **MISSING** | Parent relation reported absent. |
| `events` indexes | `events_tenant_workspace_order`, `events_approval_order` | **MISSING** | Parent relation reported absent. |
| `evidence_objects` columns | Ordered columns: `event_id text` PK, `organization_id text`, `tenant_id text`, `workspace_id text`, `encrypted_content bytea`, `ciphertext_sha256 text`, `created_at timestamptz`; composite FK to event; tenant-equals-org check | **MISSING** | Parent schema reported absent. Evidence plaintext is not stored by this table. |
| `approvals` columns | Ordered columns: `approval_id text` PK, `organization_id text`, `tenant_id text`, `workspace_id text`, `requesting_actor text`, `decision_event_id text`, `evidence_event_id text`, `state text`, `workflow_stage text`, `current_approver_role text`, `version integer`, `last_event_id text`, `created_at timestamptz` | **MISSING** | Parent schema reported absent. |
| `approvals` constraints | Tenant-equals-organization check; state check (`PENDING`, `ESCALATED`, `APPROVED`, `REJECTED`, `COMPLETED`, `CLOSED`); stage check (`FINANCE`, `CIO`, `CEO`); approver-role check (`finance`, `cio`, `ceo`); `version > 0`; unique `(approval_id, organization_id, tenant_id, workspace_id)`; composite decision/evidence FKs; composite last-event FK deferred initially | **MISSING** | Parent relation reported absent. |
| `approvals` index | `approvals_tenant_workspace` | **MISSING** | Parent relation reported absent. |
| `evidence_objects` constraints | PK `event_id`; tenant-equals-organization check; composite FK `(event_id, organization_id, tenant_id, workspace_id)` to the matching `events` key | **MISSING** | Parent relation reported absent. |
| `events` check/unique/FK details | Event-type allowlist of seven V1 events; `tenant_id = organization_id`; conditional non-null `approval_id`; unique `(organization_id, tenant_id, idempotency_key)` and `(event_id, organization_id, tenant_id, workspace_id)`; three nullable composite self-FKs from `ask_event_id`, `decision_event_id`, `evidence_event_id` plus org/tenant/workspace to the matching event scope | **MISSING** | Parent relation reported absent. Constraint names are not explicitly assigned in the SQL; compare definitions rather than assuming generated names. |
| `jwt_verification_settings` secret population | Provisioner upserts signing secret and issuer | **MISSING / not safe to infer** | Script behavior is local source evidence; target row is not reported. A secret may not be read back for assessment. |
| `nxr_customer_workflow_owner` | NOLOGIN, NOSUPERUSER, NOBYPASSRLS, owns workflow schema/objects and security-definer functions | **MISSING** | Owner/runtime roles are reported absent. |
| `nxr_customer_workflow_runtime` | NOLOGIN, NOSUPERUSER, NOBYPASSRLS; least-privilege app role membership | **MISSING** | Owner/runtime roles are reported absent. |
| `nxr_customer_workflow_app` | Login, no superuser/create-db/create-role/BYPASSRLS; member of runtime only | **UNVERIFIED** | Finding reports owner/runtime roles absent, not this login role. Check role attributes and all memberships; no password hash should be selected. |
| `anon`, `authenticated`, `service_role` | Existing Supabase roles are named in migration revokes | **UNVERIFIED** | No role inventory was included in the live findings. Do not alter managed roles. |
| V1 functions | `require_evidence_object`, `verified_subject`, `verified_scope`, `enforce_event_contract`, `reject_event_mutation` | **MISSING** | Parent schema reported absent. Exact owner, ACL, volatility, and fixed `search_path` must be checked after an authorized migration. |
| V1 triggers | `enforce_customer_workflow_event`; `customer_workflow_events_no_update`; deferred constraint trigger `customer_workflow_evidence_object_required`; `customer_workflow_evidence_no_update` | **MISSING** | Parent schema/relation reported absent. |
| V1 workflow RLS | RLS enabled and forced on `events`, `evidence_objects`, `approvals` | **MISSING** | Parent relations reported absent. |
| V1 policies | Seven: `customer_workflow_profile_self`, `customer_workflow_profile_scope_guard`, `events_runtime_scope`, `events_owner_scope`, `evidence_runtime_scope`, `approvals_runtime_read`, `approvals_owner_scope` | **MISSING** | Workflow policies cannot exist without relations; public `users` absent. Policy definitions must be revised with identity option B; do not install public-user policies. |
| Policy contract | Identity self/scope policies restrict mapping reads to verified Auth subject and org; `events_runtime_scope` checks verified actor/tenant and event authorization; `events_owner_scope` limits owner reads; `evidence_runtime_scope` checks verified membership; `approvals_runtime_read` is tenant-scoped read; `approvals_owner_scope` constrains approval writes. | **MISSING** | Current policy relations are absent; all mapping predicates must be rewritten and independently security-reviewed for option B. |
| Workflow grants | Runtime: schema USAGE, event/evidence SELECT+INSERT, approvals SELECT, verified-subject/scope EXECUTE; explicitly no workflow UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER. Owner: approval SELECT/INSERT/UPDATE and event SELECT, no login/BYPASSRLS. JWT settings denied to runtime. | **MISSING** | Roles/schema absent. Verify effective privileges including inherited memberships and PUBLIC defaults after an authorized migration. |
| `public.users` | RLS-enabled identity membership rows with `auth_user_id`, `org_id`, `role` and application profile fields | **MISSING** | Explicitly reported absent. This is a hard precondition in the current migration, repository contract, and recovery verifier. |
| `public.organizations` | Supabase API membership resolver selects `id,name,status` | **UNVERIFIED** | Not included in supplied findings. Minimal check: `to_regclass('public.organizations')`, columns/owner/RLS/policies, and current API exposure. |
| `auth` | Supabase-managed Auth schema, not restored or modified by V1 tool | **PRESENT** | Reported present. Internal tables/data and grants are preservation-only; do not enumerate sensitive row contents. |
| `data_fabric` | Historical G07 schema with 10 tables | **PRESENT** | Reported present. |
| G07 table RLS/policies | RLS enabled, not forced, zero policies | **PRESENT as reported** | Preserve this exact state; it is not acceptable V1 tenant isolation and must not be “fixed” as part of this migration. |
| `supabase_migrations` history | One recorded version `20260904042847_enforce_relationship_timestamp_order` | **PRESENT** | Reported. The local V1 provisioner does not insert a migration-history record. |
| Recovery targets | Proposed RPO ≤24 hours and RTO ≤4 hours | **UNVERIFIED** | Owner acceptance and timed off-host measurement remain outstanding; no migration or recovery is authorized by this plan. |
| Cross-schema dependencies / non-system grants | Must not touch Auth/G07 or unreviewed public objects | **UNVERIFIED** | No supplied complete dependency/grant result. Use the prepared read-only preflight and add the targeted checks below. |

## Constraints on the current migration and provisioner

1. The migration raises before doing DDL when `public.users` is absent.
2. Its `IF NOT EXISTS` clauses do not validate the shape of an already
   existing relation, extension, role or index. Same-name but incompatible
   objects can pass an existence check.
3. It replaces named policies and triggers using `DROP ... IF EXISTS` followed
   by `CREATE`. This is not a harmless rerun if objects with those names
   already exist.
4. It makes cross-schema changes on `public.users` and requests
   `pgcrypto WITH SCHEMA public`; both are inappropriate assumptions for the
   reported target without review.
5. It calls `public.hmac` directly. `pgcrypto` being installed under
   `extensions` does not prove that `public.hmac` exists or is callable.
6. The provisioner executes the migration, upserts a database JWT signing
   secret, creates/alters `nxr_customer_workflow_app` including its password,
   grants runtime-role membership, and performs role/RLS checks. This is a
   write-bearing administrative script, not a read-only preflight.
7. Neither that provisioner nor the logical recovery tool records the V1
   migration in the Supabase migration history. A future migration must use
   the approved migration/ledger mechanism and preserve the existing version.

## Smallest additional checks needed before final executable SQL

These are targeted, read-only checks only; they do not authorize any writes.

The following snippets are review artifacts only. They were not executed and
must be run only through an authorized read-only connection; the first checks
catalog symbol placement without returning function bodies or key material:

```sql
SELECT extension.extname,
       extension.extversion,
       extension_schema.nspname AS extension_schema,
       function_schema.nspname AS function_schema,
       procedure.proname,
       pg_get_function_identity_arguments(procedure.oid) AS identity_arguments,
       pg_get_userbyid(procedure.proowner) AS function_owner,
       procedure.proacl::text AS function_acl
FROM pg_extension AS extension
JOIN pg_namespace AS extension_schema
  ON extension_schema.oid = extension.extnamespace
LEFT JOIN pg_proc AS procedure ON procedure.proname = 'hmac'
LEFT JOIN pg_namespace AS function_schema
  ON function_schema.oid = procedure.pronamespace
WHERE extension.extname = 'pgcrypto'
  AND (procedure.oid IS NULL
       OR pg_get_function_identity_arguments(procedure.oid) = 'bytea, bytea, text')
ORDER BY function_schema.nspname, procedure.proname;
```

Separately, inspect only the proposed migration principal’s identity and
effective database/schema privileges, plus the existence/columns/RLS metadata
for `public.organizations`. Do not select `pg_authid`, password verifiers,
signing secrets, Auth rows, or function source from managed schemas. The
principal’s exact role must be selected by the owner; do not substitute
`postgres` or infer superuser access.

1. **Extension symbol:** identify `pgcrypto` namespace and the exact `hmac`
   overload (`bytea, bytea, text`) in every schema, plus visibility/execute
   rights for the intended non-login roles. The plan must use the observed
   safe qualified symbol; no extension relocation is assumed.
2. **Provisioning ability:** capture `session_user/current_user`, role
   attributes, `has_database_privilege(..., 'CREATE')`, relevant schema
   `CREATE` privileges, and whether the authorized migration principal may
   create/alter only the proposed roles. Never select `rolpassword`.
3. **Application organization contract:** check existence and metadata for
   `public.organizations` because current `backend/supabase_auth.py` reads it.
   The proposed isolated mapping must decide the authoritative organization
   name/status source.
4. **Migration registry:** read schema/table metadata and the existing V1
   version/hash if any; confirm the supported Supabase migration history
   mechanism and whether the prior migration is applied by the provider
   ledger. Do not insert or edit history during preflight.
5. **Auth signing configuration:** obtain a read-only, non-secret
   configuration confirmation of active JWT algorithms/key IDs, issuer,
   audience, rotation/overlap and session revocation behavior. Never request
   or export signing key bytes.
6. **Protection snapshots:** obtain sanitized before-state catalogs for all
   G07 relations/functions/ACLs/policies, Auth schema metadata, migrations,
   extensions, roles/memberships, and database/schema grants. Current user
   findings do not establish this full baseline.

## Reproducible target contract after identity redesign

The three workflow tables must have the exact column order and types checked
by `_verify_catalog` in `postgres_v1_workflow_recovery.py`. Target acceptance
also requires matching PK/unique/check/FK constraints and named indexes;
the exact function definitions/owners/security/search paths; four named
triggers; forced RLS on the three data tables; seven reviewed policies
rewritten for the approved mapping schema; no unauthorized grants; and an
empty event/evidence/approval target. Current recovery code explicitly checks
for `public.users` and the seven legacy-named policies, so option B also
requires a versioned recovery-tool contract update and regression tests before
it can consume a newly mapped target.

No migration SQL was executed or supplied to the cloud. The existing project
is a **conditional technical candidate only**, not a presently compatible
restore target. Gate 1 remains **BLOCKED**.

## Planning decision and smallest unblock

**PLAN BLOCKED** for a final executable migration because two compatibility
facts determine the identity/JWT implementation: the exact callable
`pgcrypto` HMAC symbol and execute rights in the observed `extensions` schema,
and the active Auth signing algorithm/key-ID/issuer/audience/rotation contract.
Also obtain the selected migration principal's actual database/schema/role
creation capabilities. The smallest next step is a read-only owner-supplied
result for those targeted checks (and a decision accepting Option B); no
general project rediscovery is requested. Once they are resolved, the local
identity adapter/migration/recovery verifier must be revised and tested
before owner review of any exact DDL. This is not permission to execute it.
