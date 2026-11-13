# SQ-DB final commit-uncertainty qualification

Recommendation: GO for SQ-DB technical acceptance within the synthetic PostgreSQL
qualification scope. The previous commit-probe blocker is closed by real driver
execution, end-to-end verified TLS and independent authoritative database reads.
This does not accept SQ-APP, public release, real human identity, current external
authority, D10 application-adapter integration or external fencing.

Driver: Python3.12.8; psycopg2-binary2.9.10; bundled libpq160000 successfully tested
against PostgreSQL17.11. Immutable local image:
sha256:3c688be4b623536ed825570efa9ddaa43ac13edc3790584b8747faacf7a75ec2.
Base, wheel hash, source hashes and public-PyPI verification are retained in
driver-provenance.json. Build and exact execution commands, fixture provenance and
fault implementation are documented in deploy/sq-db/commit-driver/README.md.

Baseline: desktop-linux; nexora-m3sq-local-20261110;
nexora_m2c_m3sq_20261110; qualified PostgreSQL digest unchanged. Both SQ-DB servers
healthy. Private network contained only the target DB before execution. Driver
shares only that network namespace, no ports or persistent storage. Prior SQL
source/evidence fingerprints were verified unchanged. Existing application
containers were not altered. No schema migrations, daemon restarts or cleanup.

## Real results (probe-r4.log / results.json)

A: acknowledged commit -> known committed; exactly one complete G08 execution set.
B: acknowledged rollback -> known rolled back; zero execution rows.
C: socket interruption before COMMIT -> client UNKNOWN, then confirmed abort only
   after backend ended and fresh database lookup showed zero execution rows.
D/E: encrypted COMMIT response held, server commit independently observed, socket
   closed -> client UNKNOWN; fresh connection reconciled known COMMITTED using
   original canonical request, operation/key, SQL-session actor, event and result.
F: replay same original operation/key denied42501; existing complete receipt retained.
G/H/I: two concurrent attempts -> one COMMITTED, one42501; exactly one consumption,
   immutable evidence record, receipt and event; no inconsistent authorization state.
   Evidence mutation denied55000; both history checkers passed after all cases.
J: held COMMIT with live backend and absent receipt -> UNKNOWN, retry denied by
   unchanged reconcile_exact; after request release, original operation reconciled
   committed. Absence alone was never treated as rollback or retry authorization.

Eight grouped scenarios cover requested A-J. Final runner exited0. A prior successful
r3 execution is also retained. Initial/r2 attempts failed closed before mutations
because inet text included /32; normalization now compares exact loopback IP while
retaining database/isolation/TLS guards. A read-only diagnostic had a shell quoting
syntax error; no state changed. All attempts retained. No remaining SQ-DB defect
was observed in final execution. This bounded fault suite is not a claim about
all possible process, disk, network or distributed-system failures.

Regression: 98 existing M2 tests passed without warnings; 8 isolation tests passed.
Final live global checkers passed inside a READ ONLY transaction; both DB servers
remain healthy. Old incomplete result records are preserved; this report and
results.json supersede their commit-probe NOT_RUN status for this scope only.

SQ-APP prerequisites: qualified exact-candidate application images and managed test
Auth, real authenticated tenant/operator boundary, operation-to-organization and
owner/current-authority adapters, external fencing and D10 reconciliation adapter,
ingress conflict resolution, product journey, encrypted persistence and coordinated
recovery/monitoring qualification. Never enable a production owner operation based
on synthetic fixture identities or technical-evidence strings.
