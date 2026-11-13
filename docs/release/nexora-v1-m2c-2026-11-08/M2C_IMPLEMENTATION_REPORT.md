# NEXORA M2-C integration and qualification results

8 November 2026, Asia/Calcutta. Branch: `program/nexora-production-activation`.

**Application safety integration implemented and offline verified. PostgreSQL and external identity/authority qualification remain OPEN.** This is working repository code, not a replacement design program. Protected production workflows now reach tested denial boundaries instead of using caller identities, separate state/history writes or synthetic success. No SQL execution, database connection, restoration access, deployment, commits/tags/pushes, credential disclosure, release-guard changes or destructive cleanup occurred.

## A. Files and integration changes

Existing application files intentionally updated, with their exact pre-M2-C source bytes retained under `prior_sources/`:

- `auth/authenticated_tenant.py:13–68`: application account-scope adapter and shared `require_protected_workflow` gate. Uses M2-B's actual unavailable identity provider through a lazy import; missing staged code in a release package is also a safe denial. A role, username, Auth UID, tenant context or caller flag never becomes owner assurance.
- `backend/routes/auth.py:239`: authenticated owner admission/revocation/invalidation/execution/receipt-reconciliation/status-reconciliation entry points at `/api/v1/auth/owner-operations/{action}`. Current account resolution is reused; cross-organization requests return 403, unverified owner paths return 503, unexpected trust/actor fields return 422. No owner operation is executed.
- `api/v1/approvals.py`: existing route paths now require the real `get_current_user` dependency. Actor and organization selectors cannot override account scope, including repeated conflicting query selectors. Unsupported reads/writes return explicit 503; removed unauthenticated service calls, raw exception exposure and fabricated empty successful audit history.
- `services/v1_approval_authority.py:193`: live adapter requires `AuthenticatedTenantContext`, scopes queries by organization AND tenant, verifies returned row tenant/request identity before conversion and parses history times. Replaced unsupported direct state UPDATE + separate history INSERT with the protected mutation gate. The old create path's undefined `workflow_stage` is also eliminated. No speculative atomic RPC was invented.
- `repositories/v1_approval_repository.py:50`: decisions reach the protected boundary before numeric-ID resolution or any remote read/write. Supplied actor must match authenticated identity.
- `services/approval_service.py:81`: legacy module-level approve/reject helpers retain RBAC denial but cannot report successful committed approval from a role check and random trace ID. They now fail closed. The two old tests that asserted synthetic success were corrected to require unavailable authority; their prior source is retained.
- `scripts/provision_production_tenant.py:72`: live provisioning stops before importing/constructing the Supabase admin client. `--approved-request` remains acknowledgement, not operator authentication. Unavailable owner authority/fencing produces `AUTHORITY_UNAVAILABLE`, exit 7. Dry-run and explicitly injected offline orchestration tests remain functional. No credentials or arbitrary provider errors are printed.
- `backend/middleware/tenant_isolation.py`: invalid/expired tokens and header-tenant mismatch now return 401/403 JSON responses directly instead of raising inside middleware and potentially producing a server failure. Existing current-account and revocation checks remain in force.
- `tests/services/test_approval_service.py`: only the two synthetic-success expectations changed, as described above.

New implementation artifacts:

- `repositories/g08_transaction.py`: supplied-connection Psycopg2 protocol adapter; no connection factory/import-time network activity. Rejects autocommit, non-idle or unknown connections; establishes READ COMMITTED before protected commands, then acquires the global lock and checks histories. Owner SQL calls use fixed function names and bound JSON parameters. SQL denial or unexpected return from a still-unqualified RPC rolls back; there is no successful PostgREST multi-request emulation. Commit errors propagate through M2-A's unknown-commit boundary. This is not a completed owner-state/unit-of-work mapper.
- `database/contracts/g08_m2c/A022_result_link_integrity.sql`: additive staged CHECK requiring nonnull `result.event_id` to match execution evidence `event_id`. This closes the SQL/Python mismatch: M2-B's coordinator already rejects inconsistent event envelopes but its SQL evidence table previously accepted any JSON object. No original migration or permission was weakened.
- `database/contracts/g08_m2c/qualification/`: executable psql bootstrap/install/test sequence, effective privilege checks, recovery probe, guarded concurrency setup/A/B scripts, real-driver unknown-commit probe and detailed README.
- `scripts/prepare_m2c_qualification.py`: filesystem-only preparation, include-path validation, source hashes and six-migration dependency inspection. No database execution option.
- `scripts/run_m2c_verification.py` and `tests/g08_integration/`: reproducible sanitized offline regression, actual route/JWT/current-account tests, adapter tests and package/interlock checks.

## B. Six-migration compatibility assessment

The six retained source files remain byte-identical. Qualification order:

| Order | Retained migration | Compatibility finding |
|---|---|---|
| 1 | `g08_m2a/S020_integrity.sql` | Eleven tables, two bounded roles, typed domains, composite unique keys and four deferred current/version/event/origin FK cycles. Immediate predecessor/authorizing-version and request/approval references have existing targets. Auth subject RESTRICT and no cascades retained. Requires `auth.users` and runtime role names. |
| 2 | `g08_m2a/A020A_enforcement.sql` | Checker/trigger definitions follow tables, explicit eleven-table visibility policies and append-only/current-provenance guards; READ COMMITTED/global lock protocol. Function ownership transfer temporarily requires CREATE, revoked at end. Ordinary execution remains closed. |
| 3 | `g08_m2a/A020A_private_writer.sql` | Typed row dependencies exist. Private invoker persistence has no runtime or business-owner EXECUTE grant; receipt/version/event/current writes remain one transaction. This is not an approval/identity verifier. |
| 4 | `g08_m2b/S021_owner_authorization.sql` | Four added tables, three bounded roles; exact predecessor FK and evidence/consumption composite unique/deferred cycles use compatible keys and types. Existing owner tables are referenced rather than replaced. Extra checker SELECT policies remain checker-only. |
| 5 | `g08_m2b/A021_owner_integrity.sql` | Separate eight-table checker composes M2-A's eleven-table checker; owner events/receipts/evidence/consumption checked bidirectionally. Every relevant immutable insertion queues deferred validation. Existing owner history without real admission/evidence fails installation rather than receiving fabricated backfill. |
| 6 | `g08_m2b/A021_owner_interfaces.sql` | Private lifecycle/current-authority/consumption primitives and closed controlled/read interfaces. No business-owner table writes, runtime RPC rights, invented validator or successful fallback. Actual operator/session/policy/D08/D10/fencing providers remain absent. |

Paths above are under `database/contracts/`. M2-C's additive `A022_result_link_integrity.sql` follows all six. A newly strict result-link constraint may reject an existing incompatible history; do not rewrite immutable data to force it through. An existing target needs a truthful compatibility migration and separately authorized scope.

Machine evidence: `qualification/six-migration-compatibility.json` reports 15 defined tables and zero forward/missing table-target issues in a regex order inspection. This is **not SQL parsing or server validation**. Keys/deferral/trigger/privilege boundaries were source-reviewed; actual PostgreSQL behavior remains unverified.

Important ordering: run the original M2-A rollback-only fixture after its three files and **before** M2-B adds mandatory owner-status/evidence requirements. Run the M2-B fixture after all six plus A022. Each installation file commits independently; writer quiescence must span the whole sequence. Do not replay CREATE files over a partial installation.

## C. Application workflow integration status

| Workflow | Implemented behavior | Still unqualified / disabled |
|---|---|---|
| Organization provisioning | Live CLI factory denies before admin-client construction; dry-run remains offline | Cross-system Auth invitation/binding + database mutation is not atomic or owner-authorized; live provisioning disabled |
| Authenticated API account | Existing signed JWT verification, token revocation, current configured account status/tenant resolution reused | Standalone API username/role is not independently verified owner identity |
| Supabase/Streamlit user | Existing `utils/auth.py:60` `login_user` authenticates through `sign_in_with_password`; UID-bound profile/session context remains intact | No assumption of owner natural-person assurance, MFA, fresh external session or fencing from that account identity |
| Tenant/organization authorization | Authenticated current account constrains API tenant/actor selectors; live approval reader enforces context + both row scope fields + request ID | No approved relation from a tenant account to a GLOBAL G08 owner operation; no `super_admin` bypass |
| Decisions / approvals | API and live repository writes now deny before remote reads/writes; removed split state/history mutation and RBAC-only committed success | Real atomic approval writer, policy and G08 mapping are not established; workflow mutation disabled |
| Ordinary approval reads | Existing UI adapter can read scoped authoritative rows with response validation | Backend API has no approved account-to-UID/projection bridge and returns 503, including history/metrics, rather than invented data |
| Owner admission / terminal status | Actual authenticated API surface wired to M2-B unavailable assurance; SQL primitives/status history preserved | No admission, revocation or invalidation can be authorized from a caller flag or role; provider and narrow adapter remain disabled |
| One-time consumption / evidence / audit | M2-B uniqueness/linkage/checkers preserved; new SQL event-result CHECK; fake success/audit responses removed | No live owner mutation is permitted, so no new successful audit/consumption record is fabricated |
| Commit acknowledgement / reconciliation | M2-A boundary reused in driver protocol adapter; M2-B receipt/status reconciliation regression passes; actual API reconciliation routes deny when D10 is unavailable | Real driver/server acknowledgement loss and authorized owner reads need PostgreSQL/external qualification; no automatic retry/fresh ID/key |

The original `ProductionTenantProvisioningService` remains the tested adapter-driven legacy orchestration behind the now-closed live factory; it is not relabeled as an authorized G08 transactional provisioning engine. Test-only injection of fake adapters is not exposed as a CLI switch or production authentication source.

The existing release allowlist remains unchanged. Active gates live in already allowlisted modules and safely handle missing staged M2 code via lazy import. The new DB adapter and staged M2 modules are intentionally not silently admitted to a deployable package. Packaging/activation remains a release prerequisite; no startup dependency on an excluded module was added without a denial fallback.

## D. Executed tests and results

```powershell
.venv/Scripts/python.exe -m scripts.run_m2c_verification
```

Final result: **326 passed, zero failures/skips/warnings**. Sixteen Python sources parsed. `git diff --check` passed; Git emitted only existing line-ending advisories for unrelated files. No real database/SQL parser was used.

The selected suite includes all seven M1 verification test files, M2-A's 28 offline tests, M2-B's 70 tests, provisioning regressions, tenant authorization foundation, existing in-memory approval contracts, corrected legacy approval-helper tests and the new application/driver/package integration tests. The exact allowlisted command and per-case results are retained in `offline/checks.json` and `offline/results.xml`; stdout is in `offline/pytest.log`.

New verification exercises genuine FastAPI routes, middleware, JWT signing/verification and current-account resolution with explicit synthetic local test accounts/keys. It covers unauthenticated requests, invalid signatures, current account disable/tenant reassignment, tenant-header and repeated query mismatches, actor spoofing, all six owner route actions, forbidden trust fields, unavailable identity, pre-network provisioning denial, scoped reader response/request validation, pre-read decision denial, fixed/bound SQL protocol order, rollback, unknown commit, rejected autocommit/active transactions, package ordering and probe interlocks. Test doubles are confined to tests and do not authenticate production users.

Verification uses an allowlisted child environment, disabled dotenv/plugin discovery and unchanged `scripts.m1_offline_guard`, which blocks network/database client activity. TestClient is in-process; permitted stdlib Windows socketpair IPC is not a service/database connection. No background service/container was started.

Preservation: **52 fingerprinted prior artifacts unchanged**, including retained M0/M1/M2-A/M2-B reports/evidence, all six migrations, M2-A/M2-B implementation/tests and release guards. Intentional application/test edits are tracked separately, with exact pre-M2-C source snapshots in `prior_sources/` and hashes in the final evidence manifest. No unrelated dirty worktree change was restored or removed. Earlier 312/318/322-pass progress runs preceded added defect-specific tests; final output is the 326-case suite above.

## E. PostgreSQL qualification status

**PREPARED_NOT_EXECUTED.** Retained instructions require separate target scope; no explicitly authorized existing isolated disposable local environment was established. No server/port/credential probing or database connection was used to infer authorization. Production, restoration and unauthorized Supabase projects were not accessed.

Preparation command:

```powershell
.venv/Scripts/python.exe -m scripts.prepare_m2c_qualification --output-dir docs/release/nexora-v1-m2c-2026-11-08/qualification
```

The package README at `database/contracts/g08_m2c/qualification/README.md` contains exact future psql/probe commands and recovery steps. It requires separate custodian authorization, a **fresh isolated disposable cluster** (roles are cluster-global), loopback endpoint, blank `nexora_m2c_...` database and explicit session acknowledgement. These interlocks are not authorization themselves. It creates only a minimal local Auth FK fixture, not a Supabase identity emulator. No environment, server, credentials or container is created by preparation.

Prepared coverage:

- Stop-on-error installation of the six originals plus A022, correctly ordered M2-A/M2-B structural suites, constraint/trigger/append-only evidence, failed transaction recovery and effective role/membership/table/RLS/RPC denials.
- Scoped application isolation tests already executed offline; database runtime callers are denied GLOBAL G08 access. Successful tenant-specific G08 ownership is not claimed because its authority binding is unresolved.
- Executable committed synthetic race setup and two overlapping-session scripts: execution waits for revocation, then rejects the fresh state with 42501. The race requires the separately authorized fixture and is NOT RUN.
- Structural replay/duplicate consumption and proof mismatch checks. Successful simultaneous authorized owner mutations remain blocked until a real owner writer and assurance/fence adapters exist; both current controlled RPC attempts must deny.
- Executable `unknown_commit_probe.py` for a real driver/session-temporary-table probe, with explicit local-target interlocks and managed libpq credentials. It simulates acknowledgement loss before/after an actual server commit and reconciles the original probe ID. It is NOT RUN and would qualify only the driver boundary, not G08/D10 or a real network partition. Offline tests verify that missing/wrong target settings reject before driver import/connection.
- Recovery retains partial output/manifests, rolls back only the open data transaction and keeps traffic disabled. Earlier installation commits/roles persist after a later-file failure. No destructive down migration, reset or disposal command is provided; use a fresh custodian-provisioned fixture under its own lifecycle authority.

Machine status and source SHA-256 values are in `qualification/qualification-manifest.json`. There is no PostgreSQL PASS, SQL grammar PASS, managed-platform privilege PASS or real external-verification PASS in this package.

## F. External identity and authority dependencies

1. **Independent owner identity/session binding**: actual accepted natural-person verifier, appointments, operator authentication and optional Auth UID attestation remain missing. Existing API account and Supabase sign-in support ordinary account scope only. M2-B `UnavailableOwnerTrust` and SQL `g08_verify_owner_trust` stay closed; application gates use that denial, not a fake provider.
2. **GLOBAL owner operation → organization permission**: `database/contracts/g08_m2a/S020_integrity.sql` owner authorizations use `scope_key='global'` and have no accepted organization ownership column. Current tenant membership alone cannot supply that authority. An explicit approved binding and current policy/independent approval validation are prerequisites; no column or semantics was invented.
3. **Atomic approval/provisioning/owner mutation interfaces**: the previous live approval writer used multiple remote requests, and provisioning spans Auth and database operations. A qualified transaction wrapper/result schema, requester/approver/operator policy and narrow database grants are absent. New adapters deliberately do not convert arbitrary JSON or unexpected closed-RPC returns into durable success.
4. **Technical execution evidence and fencing**: independent verifier/source, freshness, successor usability and Auth/session invalidation/fence protocol remain unresolved. Owner approval or a stored hex digest is not a technical-control PASS. DB advisory locks alone cannot serialize external Auth operations.
5. **D08 and D10**: accepted canonical bytes/vectors, digest implementation, exact mutation/result binding and current receipt/status read projections remain required. The new adapter's JSON serialization is transport only. Reconciliation absence/denial/inconsistency never permits a blind retry or fresh operation/key.
6. **Authoritative resolution identity**: no DBR-01 v0.2/v0.3 artifact has been identified in the retained repository; the existing G08 contract resolution v0.2 is a different document. No missing approval was fabricated. M2-A/M2-B reports retain precise source references and open dependencies; their acceptance as independent offline scopes does not establish those external interfaces.

Detailed retained basis: `deploy/staging/NXR-CLOSE-016/G08_D02_D03_DATABASE_RESOLUTION_ADDENDUM_V0_1.md:301`, `:325`, `:374`, `:424`, `:440`, and the M2-A/M2-B implementation reports. Actual target role/default/inherited privileges, all protected invalidators and legacy overloads still require catalog/runtime qualification.

## G. Remaining release blockers

- PostgreSQL grammar, installation, FK/constraint timing, rollback/concurrency, managed-role feasibility, RLS visibility/effective privileges and full-history checker performance remain unexecuted qualification items.
- Owner execution, provisioning and approval mutations are intentionally unavailable until real trust, atomicity, scope, canonicalization, result and reader interfaces are qualified. This is a visible availability restriction, not operational completion.
- No complete live catalog/all-writer/external Auth fencing inventory or current authority projection has been qualified. Source gates do not prove all target privileged/legacy paths are closed.
- New staged modules/adapter are outside the unchanged release allowlist. A future reviewed packaging change, runtime image qualification and exact-candidate hosted CI/release controls are still required before activation.
- M0/M1 external qualification items and existing G08 Gate A/B2, staging/production and credential-custody controls remain in force. No new acceptance or deployment authority is inferred from this implementation.

## H. M2-C completion recommendation

Recommend accepting the **implemented application safety integration and reproducible offline scope**. The application now denies unsupported identity/authority paths at actual workflow entry points and avoids false committed-success/audit claims. Keep full M2-C PostgreSQL/external qualification OPEN. Do not enable owner/provisioning/approval writes, claim production readiness, or mark database/security controls accepted from the offline results.

## I. M3 infrastructure preparation instructions

1. Retain all prior evidence and six migration hashes, A022, source snapshots and final M2-C manifests. Freeze the exact candidate and resolve source-version/authority-interface dependencies before activation changes.
2. Obtain named custodian authorization for a fresh isolated disposable local cluster: exact host/port/database/role, version, no production/restoration connectivity, managed credentials, local evidence location and disposal/recovery owner. Do not infer authorization from installed binaries or a loopback service.
3. Prepare the local fixture under that separately permitted scope, then run the package commands with stop-on-error. Retain exact version/source hashes/SQLSTATE/effective grants/RLS results. Run overlapping revocation tests and the driver probe; distinguish structural synthetic fixtures from real external identity qualification.
4. Provision real operator/validator identity and assurance/fence integrations, approved operation-to-organization binding, independent approval policy, D08/result contracts and D10 reads. Never use a mock verifier, service key, API role or owner approval as proof of these controls.
5. Implement/qualify the actual atomic owner/approval/provisioning adapter only against those established contracts. Preserve global lock-before-read/row-lock order, READ COMMITTED, protected database decision time, one-time consumption, complete immutable evidence and COMMIT acknowledgement. Hold execution disabled on dependency outage or unknown commit.
6. Qualify all writer/invalidator/legacy paths, current membership/session denial, managed-role grant/default/membership paths, full-history checker visibility/performance and real driver interruption/reconciliation. Keep immutable history intact; no fabricated status/evidence backfill.
7. Prepare reviewed packaging/runtime-image and ingress/secret/network/telemetry infrastructure changes under their own release scope. Do not change the existing release guards or publish/deploy merely to test these adapters. M3 preparation is not deployment, SQL target access, commit/tag/push or production activation authority.

Implementation references consulted: official PostgreSQL [trigger timing](https://www.postgresql.org/docs/17/sql-createtrigger.html), [READ COMMITTED snapshots](https://www.postgresql.org/docs/17/transaction-iso.html), [function security](https://www.postgresql.org/docs/17/sql-createfunction.html), and Psycopg2 [connection transaction control](https://www.psycopg.org/docs/connection.html). Documentation review is not target execution evidence.
