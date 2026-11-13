# NEXORA V1 — Local PG17 Compatibility Engineering

## Result

**LOCAL COMPATIBILITY GO — the revised private identity and PostgreSQL 17
logical-recovery contract passed its required local regression checks.**

**Gate 1 independent recovery remains BLOCKED.** No Supabase connection or
write, migration, identity provisioning, package upload, restore, spend,
commit, push, or deployment was performed. No customer browser journey was
repeated. G08 remains fail-closed.

## Contract implemented

The canonical migration
[`001_customer_workflow_postgres.sql`](../../../database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql)
creates two application-owned schemas:

- `nexora_identity.memberships`: immutable Auth subject UUID, organization
  and tenant UUIDs, organization name, optional workspace scope, constrained
  application role, and `active`/`revoked` status. The primary key is
  `(auth_user_id, org_id)`, and `tenant_id = org_id` is enforced.
- `nexora_customer_workflow`: JWT verification settings, append-only events,
  encrypted evidence objects, and trigger-maintained approvals/export
  references.

Forced RLS applies to the membership table and all three workflow data
tables. The mapping is read-only to the runtime role and row-filtered by the
cryptographically verified subject. Role, tenant, actor and workspace scope
are rechecked by SQL functions, triggers and policies; caller-supplied values
alone cannot authorize a workflow operation. Multiple active organization
mappings are treated as ambiguous and rejected. Revoked or missing mappings
are denied. Workspace-bound mappings see only their mapped workspace; a
NULL workspace mapping is organization-scoped.

Supabase Auth remains the authentication authority. The backend verifies the
Auth user through the supported Auth API and resolves membership from the
private application schema. It does not read Auth internals or use
`public.users` for the V1 membership contract. Finance, CIO and CEO
(`executive`) approval identities continue to be checked against mapped
application roles and preserved actor UUIDs.

The migration does not relocate or recreate `pgcrypto`. It locates the
extension-owned `hmac(bytea, bytea, text)` function in its installed schema,
then grants only schema USAGE and function EXECUTE on that symbol to the
non-login V1 owner role. No wrapper or broad role grant is added. The
destination's reported `extensions` placement is simulated by the PG17
target test. Whether Supabase authorizes this exact narrow schema ACL change
remains unverified.

JWT verification is deliberately local-only. SQL settings default to
`verification_mode='disabled'`; backend/provisioner accept only
`synthetic_hs256` in explicit local, test or qualification environments.
Production provisioning and token verification fail closed until the real
Supabase JWT algorithm, issuer, audience, key identifiers, rotation and
revocation contract are independently established. Synthetic keys are not
production keys.

The PG17 recovery package is format `nexora-v1-workflow-logical-v2`. It
includes encrypted workflow events/evidence, approval state and
`identity_mappings.jsonl`, but no Auth rows, global roles, secrets, or G07
objects. The target must have matching application identity mappings
provisioned separately by an authorized owner; the runtime restore credential
cannot insert or update membership. The verifier compares target mappings
with the package, checks forced RLS/owners/policies/grants and exact
`pgcrypto` function access, restores the workflow in one serializable
transaction, and refuses duplicate/non-empty restore targets.

The existing PostgreSQL 18 full-recovery implementation was not changed.

## Files changed

- `database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql`
- `backend/supabase_auth.py`
- `scripts/provision_customer_workflow_postgres.py`
- `scripts/postgres_v1_workflow_recovery.py`
- `tests/customer_workflow/test_customer_workflow_postgres.py`
- `tests/security/test_supabase_api_auth.py`
- This report and the five existing Gate 1 assessment records,
  `AUTHORIZATION_CHECKLIST.md`, and `DESTINATION_ASSESSMENT.md`.

The PostgreSQL repository continues to set the verified Auth token and
transaction-local tenant/actor context; authorization is now checked against
the private identity contract by the migration functions and RLS.

## Local test environment and results

- Source: isolated synthetic PostgreSQL 18 cluster created by the existing
  local test fixture.
- Recovery target: disposable local PostgreSQL **17.12** container
  (`postgres:17`, image digest
  `sha256:846a7ddaa67a4b354ae1d21087b683901aa6113a4ed626d3787cfbf6c85e3e07`)
  with
  Supabase-like managed roles/schemas, historical Auth/G07 sentinels, an
  existing migration record, and `pgcrypto` installed in `extensions`.
- Test command:

  ```powershell
  $env:NEXORA_CUSTOMER_WORKFLOW_LOCAL_PG='1'
  $env:NEXORA_V1_LOGICAL_PG17_IMAGE='postgres:17'
  .\.venv\Scripts\python.exe -m pytest tests\customer_workflow `
    tests\security\test_supabase_api_auth.py `
    tests\security\test_api_auth_tenant_authorization.py `
    tests\security\test_token_store_revocation_contract.py `
    tests\security\test_tenant_scoped_data_access.py -q --disable-warnings
  ```

- Result: **80 passed, 0 failed, 0 skipped**.
- The PG17 drill separately passed **1/1** before the combined suite. The
  combined suite includes the same PG17 test.
- Coverage includes migration replay/idempotency; valid, missing, revoked,
  ambiguous, workspace-scoped and cross-tenant identity mappings; protected
  runtime privileges; extension-schema HMAC resolution; encrypted evidence,
  Ask/decision/Finance-CIO-CEO approval and evidence-linked export recovery;
  wrong backup key/key ID/target JWT; truncated package; incompatible
  migration hash; missing RLS policy; invalid recovery credentials; injected
  mid-restore interruption with zero partial commit; duplicate restore
  refusal; restored Customer A access and Customer B denial; and before/after
  preservation snapshots of roles/memberships, protected schema owners/ACLs,
  Auth, G07, migration history, public objects, extension version/schema/
  owner, the extension HMAC function ACL/definition hash, and identity rows.
- The test command exited successfully. Pytest emitted a non-fatal Windows
  temporary-directory cleanup `PermissionError` from its atexit handler;
  this happened after the passing result and did not change the exit status.

No Supabase compatibility is inferred from this local test. In particular,
the independent target used synthetic identities and was not connected to
Supabase Auth or the nominated project.
The nominated project was reported as PostgreSQL 17.11; this local PG17.12
test verifies major-version compatibility, not an exact minor-version clone.

## Migration and test commands

For a disposable local qualification only, use the test command above. To
apply the provisioner in a disposable local database, explicitly provide a
local migration DSN, local runtime password, synthetic signing key and
synthetic issuer, then run:

```powershell
$env:ENVIRONMENT='test'
$env:NEXORA_CUSTOMER_WORKFLOW_JWT_MODE='synthetic_hs256'
.\.venv\Scripts\python.exe -m scripts.provision_customer_workflow_postgres
```

The provisioner refuses production or unmarked JWT modes, and its settings
upsert refuses to rotate an existing signing key. **No production/cloud
migration command is provided or authorized.** Before one can be prepared,
the production JWT verifier, Supabase migration principal privileges,
extension ACL impact and provider-supported migration ledger must be
approved and verified read-only. The target identity mapping must be
provisioned separately under explicit owner authorization.

## Remaining production blockers and approvals

1. Read-only confirmation of production JWT algorithm(s), issuer, audience,
   key IDs, rotation/overlap, and session revocation behavior. Until then,
   production auth/JWT verification is disabled.
2. Read-only confirmation that the selected Supabase migration principal can
   create/own only the proposed roles/schemas and apply the narrowly scoped
   `extensions` schema/function grants; no managed role changes or
   `BYPASSRLS` are assumed.
3. Owner/security review of the identity mapping lifecycle, role assignment,
   workspace scope, migration hash, extension ACL delta, package identity
   mapping process, and recovery operator/key custody.
4. Current exact-project catalog and protected-object snapshots, including
   G07/Auth/migration/role/grant preservation. Supplied point-in-time catalog
   findings do not establish this full baseline.
5. Explicit owner acceptance or revision of proposed RPO ≤24 hours and RTO
   ≤4 hours, followed by authorized off-host testing with measured results.
6. Verified itemized incremental cost within ₹1,000, explicit execution and
   restore authorization, retention/cleanup authority, operational ownership,
   and a genuinely independent destination. None is established by local
   tests.

The PG18 full package remains unsuitable for the managed PG17 destination.
This local implementation does not authorize or claim the independent
Supabase restore, production readiness, RPO/RTO compliance, or V1 production
activation. **Gate 1 remains BLOCKED.**
