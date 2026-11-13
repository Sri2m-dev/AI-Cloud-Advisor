# Gate 1 — Identity Contract Decision

Target: fixed Supabase restoration project `uuqprdnqhbsmwubeqouw`
Assessment: 2026-11-13; local design review only
Decision: **Recommend Option B — isolated application identity mapping.**
This is a design recommendation, not an accepted implementation or an
authorization to alter the project.

## Local implementation update

Option B has been implemented in the local V1 contract. The private
`nexora_identity.memberships` table maps Auth UUID to tenant/organization,
application role, active/revoked status, organization name and optional
workspace scope. The backend verifies the Supabase Auth user and resolves
exactly one active mapping; SQL `verified_scope`, event-contract checks and
forced-RLS policies recheck that mapping. No mapping lookup reads
`public.users`, and no migration writes to `auth.*`.

The application currently enables only the synthetic HS256 verifier in
explicit local/test/qualification environments. SQL defaults to
`verification_mode='disabled'`; the production JWT algorithm, issuer,
audience, key IDs, rotation and revocation contract remain unverified and
fail closed. The PG17 logical package includes and verifies identity mapping
records, but the restore tool does not let the runtime role create mappings;
the target must receive matching mappings through an independently
authorized owner-only provisioning step before workflow restore.

The following design comparison records the assessment baseline. The
implementation results and limits are in
[LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md](./LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md).

## Existing verified application contract

The authenticated application currently treats Supabase Auth as the identity
provider and resolves customer membership through REST resources in `public`:

- [`backend/supabase_auth.py`](../../../backend/supabase_auth.py) verifies
  access JWTs with configured HS256 key, issuer, and audience; requires
  `sub`, `session_id`, `iat`, `exp`, `iss`; checks local token revocation;
  calls `auth/v1/user`; then reads `rest/v1/users` and
  `rest/v1/organizations` using the user's bearer token. It binds profile
  `auth_user_id` to the Auth UUID and requires active organization membership.
- [`AuthenticatedTenantContext`](../../../auth/authenticated_tenant.py)
  requires a UID-bound Supabase profile and a verified access token.
- The PostgreSQL migration and
  [`PostgresCustomerWorkflowRepository`](../../../services/postgres_customer_workflow_repository.py)
  use `public.users` to verify UID, organization and role under RLS.
- The PG17 recovery package exports only actor UUID, organization UUID and
  role mappings; it does not restore Auth users or signing secrets.
- The supplied live catalog finding says `public.users` is absent. The
  presence and shape of `public.organizations` are not established.

Thus, “Supabase Auth is present” does not provide the missing customer
organization/role membership contract.

## Options

| Option | Code compatibility | Identity, tenant and approval guarantees | Auth/JWT/RLS and security impact | Changes and risk |
|---|---|---|---|---|
| **A. Minimal application-owned `public.users` compatibility table** | Highest short-term compatibility: current resolver, migration, workflow functions and recovery verifier expect `public.users`. It still needs organization metadata compatible with `public.organizations`. | Can preserve stable Auth UUID and per-org role rows; Finance/CIO/CEO decisions remain tied to actor UUIDs and DB role membership. | Creates an application-owned object in Supabase's shared `public` API schema; requires correct RLS and PostgREST exposure. Must not create Auth users or treat email as identity. JWT key must match DB verifier; current migration's `public.hmac` is not proven. The canonical migration drops/recreates named policies on `public.users`. | Fewest application edits but greatest namespace/API coupling. Risk of collision with future Supabase/project schema, accidental broad table exposure, duplicate identity sources and divergent organization status. Not recommended for a project preserving managed Auth and G07. |
| **B. Isolated application identity schema and explicit mapping** | Requires changing the SQL contract, backend membership lookup, migration/provisioner and PG17 recovery checks; current code is not directly compatible. | Auth UUID remains the stable actor key; mapping key `(auth_user_id, organization_id)` permits multiple tenant memberships with an explicit role/status. Approval stages continue to authorize Finance → CIO → CEO from the mapped role. | Keeps Auth as authentication authority and puts application membership data outside `auth` and `public`. Use explicit non-login owner/runtime roles, narrowly exposed resolver, RLS and fixed search paths. It still needs a defined bridge from verified Supabase token claims to DB checks; do not trust client-supplied role/org or expose signing keys. | More code/test work, but clear ownership boundary and no modification of managed Auth internals. Must avoid a broadly readable identity table and prevent an app role from granting itself memberships. **Recommended.** |
| **C. Narrow Supabase Auth adapter** | The existing backend already has an Auth adapter, but it currently requires `public.users` and `public.organizations`; Auth itself does not supply Nexora organization roles. | Auth verifies identity, not Finance/CIO/CEO membership. A separate authoritative membership store remains required for stable per-tenant roles. | Least direct impact on Auth internals if the adapter uses supported Auth APIs. It does not by itself solve the missing membership data or make the database verifier compatible with the project's signing-key algorithm/rotation. | Requires adapting the backend to a private mapping store (therefore an identity mapping schema in practice). Direct queries into `auth` internals or service-role credentials from the browser are rejected. |

## Recommendation: Option B, with Auth as the authentication authority

Create a separately owned, application-private identity mapping contract in a
future reviewed migration, not `public.users` and not `auth.*`. The mapping
must use the immutable Supabase Auth UUID as actor identity and contain only
the application-owned organization membership, role, status and minimum
authorization attributes required by the V1 flow. Its role vocabulary must
match verified application roles: `finance`, `cio`, and `executive` (the
application's CEO approver is represented as `executive`; the database
approval stage/current-approver value is `CEO`/`ceo`). It must not duplicate
passwords, tokens, emails unless necessary, or Auth-managed profile data.
Customer B must not be able to read or mutate Customer A's membership.

Required implementation work before SQL is final:

1. Change the backend membership resolver from PostgREST `users` /
   `organizations` to a narrow server-side adapter for the private mapping.
   Keep the existing Auth JWT verification, `auth/v1/user` identity binding,
   revocation checks and fail-closed membership response.
2. Change `verified_scope`, event trigger checks and RLS policies to use the
   new mapping contract. No caller-provided `organization_id` or `role` may
   become authoritative without a matching verified token subject and active
   mapping row.
3. Update the migration's public-users precondition/grants/policies and the
   PG17 recovery tool's catalog verifier, source profile export and target
   profile validation. Update focused PostgreSQL/A-B, approval-role, JWT and
   restore tests. The recovery path remains opt-in.
4. Preserve distinct authorized identities for requester, Finance, CIO and
   CEO/executive; each approval event must record the mapped actor and role. A
   role string alone is not proof of distinct human identity.
5. Keep Auth as the authority for authentication and token validity. The
   database must validate the exact trusted signature/issuer/audience/subject
   contract and membership; do not bypass Auth or write to its managed tables.

This is a recommendation for implementation design, not an assertion that
the application or SQL has already been adapted. The existing V1 browser
flow and PostgreSQL test fixtures still depend on `public.users`.

## JWT and key dependency — unresolved

The existing backend verifies HS256 and requires `session_id`/`iat`, then
checks the revocation store. The SQL `verified_subject()` accepts HS256,
issuer, `role=authenticated`, authenticated audience, UUID `sub`, `exp`, and
optional `nbf`; it does not validate `session_id`, `iat` or the backend
revocation store. The provisioner stores `NEXORA_CUSTOMER_WORKFLOW_JWT_SECRET`
and issuer inside a protected workflow table and uses `ON CONFLICT DO UPDATE`
to replace those settings, while the repository forwards
the access token in transaction-local PostgreSQL settings.

The project’s active signing algorithm/key IDs, secret availability to an
approved custodian, rotation/overlap behavior and exact issuer/audience are
not established by the supplied findings. Do not copy Supabase signing keys
to the database or weaken backend validation. Before any migration design is
approved, select one safe approach:

- a supported asymmetric/JWKS verifier in the database contract; or
- a separately managed application signing key with a documented, bounded
  token exchange/attestation from the already-verified Auth backend; or
- a managed-compatible token-verification adapter that preserves revocation
  and role/tenant binding.

This selection needs a security-owner review and tests. The observed
`pgcrypto` placement in `extensions` also conflicts with the migration's
hard-coded `public.hmac` reference until the exact callable symbol is checked.

## Decision status

**Option B recommended; identity implementation and JWT bridge unqualified.**
No identity rows, Auth settings, project objects, or secrets were changed.
This plan does not authorize creation of a compatibility table, migration,
user, or role.
