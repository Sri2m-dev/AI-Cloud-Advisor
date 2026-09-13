# CMP-P6-SC-001 - Nexora v1 Current Application Schema Contract

**Status: BLOCKED_V1_SCHEMA_CONTRACT**

## Contract result

The new v1 contract is documented in
`application_schema_contract.md` and covers exactly the 34-object DEF-003
matrix. Current code supports explicit dispositions, but it does not provide
safe E1-E4 evidence for the complete keys, columns, tenant policies, and
canonical authority boundaries required to create all active public objects.

No speculative E5 DDL was added. In particular, no guessed schemas were added
for application registry, application spend mapping, approval requests/history,
technology inventory, or financial mart/KPI objects.

Disposition counts:

| Disposition | Count |
| --- | ---: |
| V1_REQUIRED | 8 |
| V1_OPTIONAL | 19 |
| LEGACY_UNREACHABLE | 6 |

The required objects with unresolved contracts remain blockers. Optional
objects are not silently promoted into the blank bootstrap.

## Tenant and authority boundaries

The existing public identity contract remains `organizations.id` with
`users.org_id`. Existing report/financial compatibility paths also use textual
`org_id` and/or `tenant_id`; no second identity system was introduced.

Data Fabric remains the canonical entity, relationship, source-fact, and
stewardship authority. Existing P1/P2 financial authorities remain canonical.
Any future public compatibility object must be explicitly labelled as such and
must not become a parallel source of truth.

## Authoritative bootstrap and migration sequence

No new SC-001 public DDL was added because the required application contracts
are incomplete. The existing bootstrap remains the known five-table baseline:
`organizations`, `users`, `clients`, `recommendations`, and `report_history`.

The executable sequence tested was:

1. Standard local Supabase-compatible harness roles and extensions.
2. `supabase/bootstrap/public_prerequisites.sql`.
3. All 17 dated public migrations in filename order.
4. Data Fabric `0001` through `0023` in numeric order.

No manual SQL was applied between migration files. The auth functions and
roles were local test harness shims only; this does not certify Supabase Auth or
PostgREST runtime behavior.

## Fresh PostgreSQL 18 replay

A new cluster was created at `.tmp/sc001-postgres`, bound to `127.0.0.1:55492`,
using the installed PostgreSQL 18 binaries. Existing PostgreSQL 14/18 Windows
services were not modified.

Result: **PASS, 41 files**

- public bootstrap: PASS
- dated public migrations: PASS, 17/17
- Data Fabric 0001-0019: PASS
- Data Fabric 0020-0023: PASS
- no migration was skipped
- failed first attempt was destroyed, then replayed from a new empty cluster

## Defects found and corrected during replay

The 0020 CASE correction compiled successfully. The required behavioral check
also passed: a valid `discovered -> classified` transition succeeded and an
invalid `classified -> canonical` transition raised the expected
`WP005_INVALID_TRANSITION` error.

The replay exposed one additional concrete PostgreSQL runtime defect in 0019:
the shared revision trigger referenced `NEW.policy_id` and other policy fields
even when firing for `stewardship_review_items`. PostgreSQL record fields are
table-specific, so the trigger failed at runtime. The smallest correction was
to place each table-specific field comparison inside its matching
`tg_table_name` branch. The migration was then replayed from a new empty
cluster and passed.

## Schema-only snapshot

A schema-only dump was produced at `.tmp/sc001-schema-only.sql` with
`pg_dump --schema-only --no-owner --no-privileges`.

- COPY statements: 0
- INSERT statements: 0
- CREATE statements: present
- client/auth/business rows: not exported

The snapshot is local certification evidence only. It is not promoted as the
deployment authority; bootstrap plus ordered migrations remain authoritative.

## Static security/tenancy result

Local PostgreSQL static checks remain applicable for RLS, grants, restricted
Data Fabric functions, append-only protections, relationship timestamp checks,
and SourceFact protections. Supabase `auth.jwt()` and PostgREST runtime
semantics were represented only by local shims and remain pending external
certification.

Result: **LOCAL_POSTGRES_CERTIFIED** for the executed migration chain;
**SUPABASE_RUNTIME_CERTIFICATION_PENDING**.

The application schema contract itself is not complete, so this does not mean
the frozen Nexora application is deployment-complete.

## Tests and artifact checks

- Focused SC-001/bootstrap/Data Fabric/stewardship suite: **37 passed**
- Full repository suite: **1862 passed, 2 skipped, 0 failures**
- Credential-pattern scan: **PASS**
- `git diff --check`: **PASS**

## Decision

**BLOCKED_V1_SCHEMA_CONTRACT**

Concrete blockers:

1. Eight V1-required public object families still lack non-speculative E1-E4
   contract evidence sufficient for authoritative DDL.
2. The tested bootstrap does not yet contain the complete current application
   public schema.
3. External Supabase Auth/PostgREST runtime certification is pending.

No staging project was created. No external systems were touched. No commit or
push was performed.
