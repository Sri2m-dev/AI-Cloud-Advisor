# NEXORA M4-G08 application reconciliation — qualification report

**Verdict: NO-GO for the application workflow.** The approved isolated G08
PostgreSQL target was created and the canonical schema/structural qualification
was applied, but no successful owner operation or application reconciliation
was executed. No operator-attestation success is claimed. The accepted M4 CFO
baseline remains GO and is preserved separately in
[`nexora-m4-cfo-integration-2026-11-11`](../nexora-m4-cfo-integration-2026-11-11/REPORT.md).

## What was deployed and verified

The exact target is `nexora-g08-r5-reconciliation-20261111`, database
`nexora_m2c_g08r5_20261111`. Its PostgreSQL 17 image is pinned to
`sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`.
The live server reports PostgreSQL 17.11. The database has one healthy container, a dedicated internal Docker network,
a dedicated named volume, and no published host port. No G08 adapter service
has been deployed. Identity details are in
[deployment-identity.json](./evidence/deployment-identity.json).

All **7** ordered canonical SQL files (S020, A020A enforcement/private writer,
S021, A021 owner integrity/interfaces, A022) were applied from the repository
qualification package. Source hashes matched the staged copies. The database
integrity fixture, owner authorization SQL fixture, effective-privilege
boundary checks, and transaction rollback/recovery checks completed with exit
code 0. Fixture writes rolled back; persistent owner authorization, identity
event, receipt, and consumption counts are all zero. See
[migration verification](./evidence/migration-verification.json) and the
[individual qualification logs](./evidence/).
The postdeployment read-only identity and owner history assertion functions
also returned successfully.

The bundled `install_and_test.sql` command emitted a PostgreSQL `NOTICE` during
the owner fixture, which PowerShell treated as a native-command error. The
migrations and preceding database fixture had completed; the remaining
owner/privilege/recovery SQL files were then run individually with notices
suppressed and each returned exit code 0. The partial initial transcript is
retained as `canonical-migration-execution.log`; it is not represented as one
uninterrupted command success.

The focused offline route/coordinator/transaction/SQL-contract suite previously
passed **139 tests**. Those tests use synthetic/fake transaction boundaries and
do not prove a live successful G08 operation.

## Existing workflow and exact blocker

The authenticated API endpoint is
[`owner_operation`](../../../backend/routes/auth.py) at
`/api/v1/auth/owner-operations/{action}`. It binds the requested organization
to the verified current account and maps `ProtectedWorkflowUnavailable` to
HTTP 503. [`require_protected_workflow`](../../../auth/authenticated_tenant.py)
still selects `UnavailableOwnerTrust`; there is no independent
session-bound operator verifier, current owner-policy/D10 provider, technical
evidence/fencing verifier, atomic `OwnerUnitOfWork`, or authorized
receipt/status projection.

After applying the canonical SQL, the same deliberate closure is present in
`g08_verify_owner_trust`: it raises `IDENTITY_ASSURANCE_UNAVAILABLE`.
`g08_control_owner_operation`, `g08_read_owner_operation_receipt`, and
`g08_read_owner_authorization_status` therefore cannot perform or return a
successful result. The reusable
[`OwnerAuthorizationCoordinator`](../../../services/g08_owner_authorization.py)
and [`execute_once`](../../../services/g08_transaction_boundary.py) implement
source-level contracts only; [`G08DbapiTransaction`](../../../repositories/g08_transaction.py)
accepts a supplied idle connection and fails closed if a closed RPC returns
unexpectedly. No application page calls the owner-operation API.

Repository inspection found no executable owner-policy/D10 or fencing
provider to connect. The canonical owner-operation schema is explicitly
`global` and has no tenant/organization field or accepted tenant-scoped
receipt projection. Inventing a policy store, tenant binding, successful
operator assertion, or replacement reconciliation engine would violate the
requested canonical/security boundary. “Owner” is an approval reference, not
proof of an operator's identity. The route and SQL owner RPCs remain closed.

## Acceptance status

- **Live PostgreSQL schema/negative structural checks:** PASS; synthetic test
  fixtures rolled back.
- **Independent operator authentication, current D10 authority and revocation,
  technical evidence/fencing, atomic successful owner execution, durable
  receipt recovery, tenant-scoped projection:** NOT QUALIFIED; providers and
  canonical tenant binding are absent.
- **Application request/status integration and actual G08 browser workflow:**
  NOT EXECUTED; no supported UI or adapter is deployed. The prior CFO browser
  qualification is not substituted.
- **G08 scenarios G08-01–G08-14:** no successful-operation scenario is claimed.
  The offline suite and SQL structural fixtures are not live application
  acceptance.

The M4 financial PostgreSQL project, identity-only Auth service, r4, and
qualified SQ-DB were not used or modified. The complete comparison verifies all
50 pre-existing container IDs/image references, 12 network IDs, and 22 volume
identities unchanged; the only added persistent service is the authorized G08
database. See
[post-deployment resource preservation](./evidence/resource-preservation-postdeployment.json).

## Remaining blockers

1. A concrete independently verifiable synthetic operator issuer/verifier and
   explicit session/tenant/operation binding.
2. An accepted owner-policy/D10 contract and evidence source, including
   permitted operation, approval/revocation freshness, and fencing semantics.
3. A canonical tenant-to-operation binding and tenant-authorized receipt/status
   projection; existing owner records are global.
4. A reviewed least-privilege atomic database adapter that implements the
   canonical G08 transaction contract without granting runtime table access or
   bypassing the closed SQL trust boundary.
5. r5 API/UI integration and live acceptance/recovery/browser tests after the
   above providers are implemented and qualified.

The target-specific authorization allowed the isolated database and canonical
qualification work performed here. It does not supply these missing technical
contracts or convert an approval reference into operator identity. No excluded
resource changed, and no commit, tag, push, or public deployment occurred.
