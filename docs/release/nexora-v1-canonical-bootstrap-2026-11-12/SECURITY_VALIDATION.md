# NEXORA V1 Canonical Bootstrap — Security Validation

## Scope and verdict

**Bounded local security checks passed; full canonical application bootstrap
security remains NO-GO.**

Validation used disposable local PostgreSQL and synthetic identities/data. The
test harness supplies local Auth-compatible functions and roles so migration
policies can be exercised; it does not certify GoTrue, PostgREST, or the hosted
Supabase authorization path.

## Verified controls

- The migration catalog assertions verified required Auth/user identifiers,
  including the `auth_user_id` UUID column, its Auth-user foreign key, and its
  partial unique index.
- Catalog checks verified the expected row-level security enablement and
  tenant-bound policy expressions for users, organizations, clients,
  recommendations, report history, and cloud-cost import tables.
- The guarded replay executed synthetic two-tenant assertions, including
  cross-tenant read isolation and rejection of an unauthorized tenant insert.
- In the same fresh database used by the customer-workflow integration test,
  Customer B could not list or resume Customer A's workspace.
- The workflow test confirmed evidence is stored encrypted: ciphertext did not
  contain the source CSV or either encryption key.
- No default-tenant behavior, customer data, or production credentials were
  introduced. G08 remains fail-closed.

Evidence: `scripts/test_only_postgres_replay.py`,
`tests/security/test_postgres_replay_harness.py`,
`tests/auth/test_tenant_authorization_foundation.py`, and
`tests/customer_workflow/test_customer_workflow_postgres.py`.

## Limitations

- Tenant contexts in the service integration test are synthetic test contexts;
  that test does not perform browser authentication.
- Local Auth shims are not equivalent to hosted Supabase JWT verification,
  GoTrue, PostgREST, or platform role behavior.
- Full application startup and every active database API call were not
  validated.
- The SQL inventory still has 29 distinct database API object names without
  creation definitions. Their data ownership, keys, joins, and tenant policies
  must come from authoritative schema sources, not guesses based on callers.
- Security validation on the disposable PostgreSQL 18.3 target does not certify
  compatibility with the reported hosted PostgreSQL 17 projects.

These results support only the narrow local tests described above. They do not
authorize production migration or activation.
