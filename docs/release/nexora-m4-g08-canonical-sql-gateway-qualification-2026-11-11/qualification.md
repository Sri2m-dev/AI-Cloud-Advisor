# NEXORA M4-G08 Canonical SQL Gateway Qualification

**Result: NO-GO.** This qualification exercised only a new disposable PostgreSQL
target. The canonical owner-operation gateway remains intentionally fail-closed;
no owner operation, live route, or protected environment was activated.

## Canonical boundary and blocker

The existing entry point is `public.g08_control_owner_operation(text,jsonb)`.
It calls `public.g08_verify_owner_trust(text,jsonb)`, which raises SQLSTATE
`55000` with `IDENTITY_ASSURANCE_UNAVAILABLE` until accepted owner-verifier,
policy, D08/D10, and fencing adapters exist. If trust verification returned,
the control function still raises `owner execution adapter unavailable`.
`public.g08_read_owner_operation_receipt(jsonb)` and
`public.g08_read_owner_authorization_status(jsonb)` likewise remain closed.
These fail-closed functions explain the current owner-operation HTTP 503.

The schema has reusable staging primitives:
`public.g08_stage_owner_admission(...)`,
`public.g08_stage_owner_status(...)`,
`public.g08_owner_decision_time(uuid,uuid)`, and
`public.g08_stage_owner_consumption(public.g08_owner_execution_evidence)`.
Consumption requires the effect/event/receipt to have already been staged in
the same transaction. The authenticated private writer in
`A020A_private_writer.sql` is not an owner writer and rejects owner-controlled
execution. The applied D10 candidate stores signed metadata and revocations but
intentionally adds no verifier, runtime grants, writer, or receipt reader.

There is no canonical owner effect/resource adapter or accepted trusted issuer
and operator-verification provider to bind an independently authenticated
operator to the SQL session. Inventing an effect writer or allowing caller
claims to satisfy this boundary would bypass the canonical model. No gateway
migration was added, and no success behavior was fabricated. D10 V1 policy
remains proposed and is not accepted production policy.

## Isolated target

| Resource | Identity |
|---|---|
| Compose project | `nexora-g08-canonical-gateway-qual-20261111-1818` |
| Database container | `nexora-g08-canonical-gateway-qual-20261111-1818-database-1` |
| Container ID | `5891a2f40d7f34bbe337fcea1eb1cba8a468611de915e96ef1c0f8b335c741f0` |
| Database | `nexora_m2c_g08gateway_20261111` |
| PostgreSQL | 17.11 |
| Image | `docker.io/library/postgres@sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a` |
| Network | `nexora-g08-canonical-gateway-qual-20261111-1818_private` (internal, bridge) |
| Network ID | `3556f84123e7e8c7ae25ee77239ea7a35e5336dd349164eb36362fbd72112bd5` |
| Volume | `nexora-g08-canonical-gateway-qual-20261111-1818_postgres` (local) |
| Host-published database port | None (`5432/tcp` has no host binding) |

Every Compose invocation used the explicit project, the single
`deploy/g08/compose.gateway-qualification.yaml` file, and the qualification
profile. The database and D10 candidate were applied only to this target. The
candidate remains marked unapplied in source and is not in an automatic
migration queue.

## Applied SQL and hashes

`database/contracts/g08_m2c/qualification/install_and_test.sql` ran its ordered
bootstrap, canonical G08 migrations, and rollback/boundary checks. The D10
candidate was then applied only to the disposable database. SHA-256 values:

| Applied file | SHA-256 |
|---|---|
| `database/contracts/g08_m2c/qualification/bootstrap.sql` | `5FA7246E9D6981F3991EA87A539A6A96173206EE4FE4CB564E6CD068CA9F9AF4` |
| `database/contracts/g08_m2a/S020_integrity.sql` | `BE9B922BD17B7551787E4A7E13E95827F14175F95492CCC7D8EA0A5B813A8DD0` |
| `database/contracts/g08_m2a/A020A_enforcement.sql` | `C05FA8A6C24FB4F78B8995825DCD7B72B88D19735979C7E6C4352953BAC0A5FE` |
| `database/contracts/g08_m2a/A020A_private_writer.sql` | `DDE62147038B2AA679E6A1BC6D2E4E494D95567E37B52715C2DE0190B6219824` |
| `database/contracts/g08_m2b/S021_owner_authorization.sql` | `C31850D0F78192C22329DA5D7ADCA7032213373D86719BA2DDEB60AFAE6D1571` |
| `database/contracts/g08_m2b/A021_owner_integrity.sql` | `C188CC6B0CEBA13B3A9592E5BAD955F899EF1308DBC294755DCBC3B145E5E90B` |
| `database/contracts/g08_m2b/A021_owner_interfaces.sql` | `33055E8A899E88A476EA44D0421F3BA14C481B16949A17EEAB5CF3792656F81C` |
| `database/contracts/g08_m2c/A022_result_link_integrity.sql` | `35B197643B3E3BB3C3CB7A52C3AFB3C52E127EB2D6DE71AB6483F06CD3194E28` |
| `database/contracts/g08_m2c/candidates/D10_persistent_authority_candidate.sql` | `49D78871A26BDFEE0482B31AD13F7619417A16FEA470B7F9ADB25314CDA9FECB` |

## Qualification evidence

| Check | Result |
|---|---|
| Focused Python G08 integration and owner-authorization regressions | 126 passed, 4 skipped; skips are environment-gated adapter tests |
| Real PostgreSQL boundary SQL | Passed: required forced-RLS tables, no `authenticated`/`service_role` DML grants, closed owner RPCs, and immutable D10 history; transaction rolled back |
| Concurrent PostgreSQL sessions | Passed: session A held the canonical transaction advisory lock; session B timed out on the same lock as expected |
| Database restart persistence probe | Passed: same database, PostgreSQL 17.11, and G08/D10 tables available before and after restart |
| Python compilation | Passed (`compileall`) |
| Ruff | Failed: 38 diagnostics in existing G08 source/tests (5 auto-fixable); no Ruff autofix applied |
| Successful owner operation / durable receipt | Not demonstrated; no authorized gateway exists |

The restart probe found zero owner authorization and zero D10 policy rows both
before and after restart. Boundary fixtures were rolled back. Consequently this
is not evidence of receipt recovery or execution durability. The lock test proves
only serialization by the existing advisory lock, not revocation/execution race
behavior.

## Preservation

The pre-qualification container snapshot contained 51 container identities.
After qualification, all 51 ID/name pairs were unchanged; there were no missing,
replaced, or unexpected containers outside the new project. The G08 r5,
SQ-DB, r4 application, r5/Auth, and financial-data project containers were
preserved. The only restart was the new disposable database container.

## Changed qualification files and remaining work

- `tests/g08_integration/postgres_gateway_boundary_qualification.sql` — the
  local-target guard now accepts loopback TCP addresses while still rejecting
  non-loopback targets.
- `tests/g08_integration/postgres_lock_session_a.sql` and
  `tests/g08_integration/postgres_lock_session_b.sql` — two-session lock test.
- `tests/g08_integration/postgres_persistence_probe.sql` — restart persistence
  probe.

No live application route was changed. No synthetic owner execution was
performed. Authorization, revocation races, duplicate-effect prevention,
unknown-commit receipt reconciliation, fencing mismatch, cross-tenant receipt
denial, and post-restart receipt recovery remain unqualified. The next safe
implementation step requires a defined canonical owner-effect/resource
contract plus an independently trusted operator/issuer and D10/D08 provider;
until then the existing 503 is the required fail-closed outcome.
