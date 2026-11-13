# Gate 1 — Security Impact Assessment

Scope: proposed V1 logical recovery schema on existing
`nexora-p3-validation-restoration` (`uuqprdnqhbsmwubeqouw`).
Assessment mode: local source review plus supplied read-only catalog findings;
no live query or cloud change performed.

## Local implementation update

The local migration no longer targets `public.users` or `auth.*`. It owns
`nexora_identity.memberships`, enables and forces RLS on it, grants the
runtime role read-only access filtered by the verified Auth subject, and
checks active role/tenant/workspace mapping in workflow authorization. The
PG17 recovery verifier checks the mapping table's owner, forced RLS,
policies, runtime read-only grants and exact package/target mapping match.
The identity table's primary key prevents duplicate per-user/per-org
mappings; multiple active organizations are rejected as ambiguous by the
backend.

`pgcrypto` is not relocated or recreated by the migration. It resolves the
extension-member HMAC function in its installed schema and grants only
`USAGE` on that schema plus `EXECUTE` on `hmac(bytea, bytea, text)` to the
non-login workflow owner. This narrowly changes the extension-schema ACL and
must be checked against Supabase's actual grant authority before any cloud
execution; no broad role grant or wrapper is created.

Production token verification remains deliberately disabled. Backend and
SQL accept only explicitly marked synthetic HS256 local/test configuration;
the exact production JWT/JWKS/key-rotation and revocation contract has not
been established. Local results are not a production Auth compatibility
claim. See
[LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md](./LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md).

## Security disposition

**Do not apply the current migration unchanged.** It aborts because the target
has no `public.users`; if that check were bypassed, it would modify policies
and grants on a public identity table, request `pgcrypto` in `public`, and
invoke `public.hmac` despite the observed extension schema being `extensions`.
The exact symbol/privilege and active Supabase JWT algorithm are not known.
Use the isolated identity mapping recommendation in
[IDENTITY_CONTRACT_DECISION.md](./IDENTITY_CONTRACT_DECISION.md) before
producing a deployable migration.

## Impact register

| Area | Current evidence / risk | Required control before authorization |
|---|---|---|
| Supabase Auth | Managed `auth` schema exists. The logical package excludes Auth data/configuration. Applying any migration to `auth.*` is out of scope. | Preserve every Auth object and record; integrate only through supported Auth API and immutable Auth subject UUID. No service-role key in browser or package. |
| G07 Data Fabric | Ten historical tables present; RLS enabled, not forced, zero policies per supplied read-only result. That is historical configuration, not a V1 isolation guarantee. | Do not modify the ten tables, their functions, policies, grants, ACLs, ownership, or data. Add a separate V1 schema only after object/dependency snapshots and approval. Do not retrofit G07 RLS. |
| Identity mismatch | `public.users` absent; canonical SQL and current backend/recovery code depend on it. `public.organizations` state is unknown. | Choose and implement identity contract B in code first; inspect organization metadata only if still needed. Require stable Auth UUID + tenant-scoped membership and no client-controlled role authority. |
| JWT signature | Backend requires HS256 and validates issuer/audience/session/expiry/issued-at plus revocation. SQL validates HMAC HS256, issuer/audience/role/subject/expiry and optional not-before, but not session ID, issued-at or revocation. | Reconcile verifier semantics and token rotation/revocation. Use only a reviewed algorithm/key design and run valid, expired, wrong issuer/audience/role, forged subject, revoked, key-rotation and wrong-tenant tests. |
| `pgcrypto` | Extension is present in `extensions`. Migration says `CREATE EXTENSION ... WITH SCHEMA public` and references `public.hmac`. | Read-only verify extension namespace, exact HMAC overload, owner and execute rights. Do not relocate or recreate the extension. In a reviewed migration, use only a verified safe schema-qualified function. |
| Owner/runtime roles | V1 group roles absent. Current SQL creates group roles in a `DO` block. Managed project role-creation capabilities were not supplied. | Read-only verify migration principal capability and role memberships. Do not assume `postgres` is superuser or grant `BYPASSRLS`; owner/runtime roles must be NOLOGIN, non-superuser and non-BYPASSRLS. |
| Application login | `nxr_customer_workflow_app` provisioner creates or alters login/password and grants runtime role. Its live existence/attributes are unknown. | Inspect attributes/memberships without password verifiers. Create or alter only with separately authorized restricted credential custody; it must not be owner, CREATEROLE, CREATEDB, SUPERUSER or BYPASSRLS. |
| Forced RLS | Canonical migration forces RLS on the three workflow data tables; G07 RLS is not forced. | Maintain forced RLS for V1; test with the actual managed role semantics and non-owner app role. Do not conflate preflight bypass role with runtime. |
| RLS policy impact | Canonical migration drops/recreates two policies on `public.users` and five workflow policies. `public.users` is absent. | Rebase identity policies onto the private mapping schema. Pre/post-compare policy definitions and ensure no permissive policy allows cross-tenant access. Require negative Customer B tests. |
| Append-only / approvals | Event trigger enforces workspace/evidence/decision links and Finance→CIO→CEO transitions; mutation triggers reject event/evidence updates/deletes. Approval state is trigger-derived and export links approval, decision, Ask and evidence. | Preserve all canonical invariants in revised functions. Snapshot function/trigger definitions and run direct SQL tamper, actor spoofing, skipped-stage, wrong-role, self-approval and unauthorized-export tests. |
| Security-definer functions | Canonical verifier/scope/contract functions use fixed `search_path` (mostly `pg_catalog`) and owner role. Function ACLs revoke public/Supabase standard roles. | Verify every security-definer function owner, fixed search path, fully qualified references and execute ACL. Add no broad `PUBLIC`, `anon`, `authenticated` or `service_role` grants. |
| Preflight credential | Recovery tool requires a separate non-superuser BYPASSRLS role with read-only checks over target workflow data. It can read across tenants by design. | Treat it as highly sensitive, one-time, short-lived, SELECT-only, non-login where feasible; restricted to a dedicated TLS connection, no owner/runtime membership, no secrets or Auth/G07 access. Grant only after explicit approval and revoke after test. |
| Recovery data/keys | Backup package is Fernet-encrypted and allowlisted. It includes encrypted event payloads, encrypted evidence, approval verification state and actor/org/role mappings; it excludes Auth data, database roles, G07, JWT secret and public profile records. | Independently custody backup/workflow/evidence keys and target JWT configuration. Verify ciphertext hashes and approval state, no plaintext in archive/logs, stable synthetic actor IDs, and encrypted export payload restoration. |
| Migration side effects | `IF NOT EXISTS` does not reconcile object shape. Named policies/triggers are dropped/recreated. Provisioner upserts the signing secret and alters or creates app login. | Use a new versioned migration with exact object allowlist, precondition assertions, migration hash, transaction and explicit rollback boundary. Do not run the current provisioner unchanged. |
| Migration history | One unrelated migration is reported. The local provisioner does not register its V1 SQL in Supabase migration history. | Define the provider-supported migration tracking mechanism and unique V1 version before execution. Preserve existing record unchanged; verify history read-only before/after. |
| Database availability | Repository maps connection/transaction failures to controlled workflow errors. | Verify restricted diagnostics and service unavailable behavior; no fallback to SQLite/legacy data or success-shaped responses. |
| Cost/recovery objectives | Incremental cost ≤₹1,000 is unverified. Proposed RPO ≤24h and RTO ≤4h remain owner-unapproved and unmeasured. | Obtain itemized dated price/FX/tax/minimums and explicit owner acceptance. Do not run recovery until cost and execution authorization are signed. |

## Exact preservation evidence required

Capture before and after the migration, using the same read-only query set and
consistent database identity, sanitized outputs and a cryptographic digest of
the output bundle:

1. **Catalog objects:** for all `data_fabric` relations and functions, plus
   `auth` and `supabase_migrations`, capture schema/relation names and kinds,
   owners, ACLs, RLS/force flags, column type/order/nullability, constraints
   and validation, index definitions/validity, policy definitions, trigger
   definitions/enabled state, and function identity arguments, owner,
   `prosecdef`, fixed `search_path`, and SHA-256 of `pg_get_functiondef`.
2. **Roles/permissions:** role attributes (never password verifiers),
   memberships/options, schema/table/sequence/function grants, default ACLs,
   and ownership for pre-existing roles and objects. Compare normalized
   records; no migration may alter managed-role flags or existing memberships.
3. **Extensions/migrations:** extension name/version/schema/owner and exact
   migration version/name/hash. The single pre-existing migration must remain
   byte-for-byte identical in its recorded values.
4. **Historical data:** catalog equality alone cannot prove row preservation.
   If a change is ever authorized, capture restricted per-table row counts and
   a deterministic cryptographic fingerprint of canonical row serialization
   for each G07 table before and after. Keep raw rows and fingerprints
   restricted; do not put customer or historical row data in this report.
5. **Auth:** capture only authorized catalog/configuration metadata and
   non-sensitive synthetic test results. Never dump tokens, secrets, password
   hashes or real Auth records into evidence.

The supplied finding that ten G07 tables exist does not provide their exact
names, functions, grants, dependencies or row fingerprints. Those remain
**UNVERIFIED** for this migration’s preservation baseline.

## Acceptance and stop conditions

Stop before any migration if `public.hmac` resolution is not established, a
required owner/runtime role cannot be created safely, any proposed object
collides, Auth/G07 snapshots are incomplete, the identity/JWT design is
unapproved, cost exceeds the cap or cannot be verified, or any baseline
snapshot differs unexpectedly. No compensating action, forced ownership,
permission widening or G07 cleanup is allowed.

This is a security review artifact only. It does not grant authorization or
certify the existing project as ready for recovery.
