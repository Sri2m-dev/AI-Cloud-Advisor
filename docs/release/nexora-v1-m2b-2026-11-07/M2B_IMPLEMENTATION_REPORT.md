# NEXORA M2-B implementation and verification

7 November 2026, Asia/Calcutta. Branch: `program/nexora-production-activation`.

**Recommendation: close the independently implementable M2-B code/offline scope; do not claim PostgreSQL qualification, accepted external identity assurance or operational activation.** Actual SQL/Python implementation and reproducible verification are delivered. All production trust routes remain closed. No SQL was executed against any database. No database/Supabase/production/restoration access, deployment, commit, tag, push, release-guard bypass or cleanup occurred.

## A. Implemented files and migration order

All existing M2-A files remain unchanged. New staged migrations are outside the automatic migration queue, following M2-A's `database/contracts` convention:

1. `database/contracts/g08_m2b/S021_owner_authorization.sql`: four append-only tables for operator assertions, authorization status history, immutable execution evidence and one-time consumption; composite/self/deferred FKs, uniqueness, forced RLS, explicit runtime denials and three bounded NOLOGIN/NOBYPASSRLS roles.
2. `database/contracts/g08_m2b/A021_owner_integrity.sql`: read-only SECURITY DEFINER checker, complete visibility assertions, M2-A checker composition, global-lock/append-only/truncate guards on new tables and deferred checks on all eight relevant new/existing owner/event tables. Installation refuses incomplete pre-existing owner history; no identity/admission/evidence is fabricated as a backfill.
3. `database/contracts/g08_m2b/A021_owner_interfaces.sql`: private admission/status/current-authority/consumption primitives; closed controlled mutation/status-read/receipt-read interfaces; explicit unavailable trust verifier. Private primitives are SECURITY INVOKER persistence functions with no runtime/business-owner grants. They do not authorize their caller.

Installation sequence, ONLY under future separate database authorization: M2-A S020, A020A enforcement, A020A private writer; then the three M2-B files in the order above, with continuous writer quiescence. Each file is transactional. A later-file failure does not undo a previously committed installation file; retain quiescence and resolve the failure under the authorized fixture lifecycle. Nothing was installed here.

`services/g08_owner_authorization.py` implements actual lifecycle validation and transaction coordination, explicit identity/authority/evidence ports, default-deny adapters, fresh post-lock reads, one-time execution, commit acknowledgement and receipt/status reconciliation. It uses M2-A's `execute_once` without editing that module. No database adapter, network SDK, application route or production identity source is configured. The release allowlist remains unchanged; this module is not activated or packaged by this work.

`scripts/run_m2b_offline_verification.py` runs the M2-A regressions and M2-B tests under the unchanged M1 offline guard, records results/source hashes and checks preservation. Test artifacts:

- `tests/owner_authorization/test_owner_authorization.py`: coordinator/lifecycle/identity/evidence/concurrency/unknown-commit tests over explicit synthetic transaction and assurance ports.
- `tests/owner_authorization/test_owner_sql_artifacts.py`: static SQL artifact assertions, not SQL execution.
- `tests/owner_authorization/postgres_qualification.sql`: UNEXECUTED rollback-only structural PostgreSQL suite.
- `tests/owner_authorization/postgres_race_session_a.sql` and `postgres_race_session_b.sql`: UNEXECUTED two-session revocation/execution freshness test, with explicit separately provisioned fixture prerequisites.

## B. Requirement-to-code mapping

S = `database/contracts/g08_m2b/S021_owner_authorization.sql`; E = `A021_owner_integrity.sql`; I = `A021_owner_interfaces.sql` in the same directory; P = `services/g08_owner_authorization.py`.

| Requirement | Exact implementation | Evidence / limit |
|---|---|---|
| Append-only owner authorization status | S:30 `g08_owner_authorization_status_history`; E new-table `g08_owner_append_only` and `g08_owner_no_truncate` triggers | No mutable status/consumed flag; no UPDATE/DELETE/TRUNCATE route |
| ADMITTED / REVOKED / INVALIDATED | S status CHECK; E `g08_assert_owner_history` status loop; I:34 `g08_stage_owner_status`; P `validate_history`, coordinator `admit`/`transition` | Initial ADMITTED; only ADMITTED → REVOKED or INVALIDATED; both terminal; tested offline |
| Exact predecessor / terminal constraint | S `(authorization_id,owner_operation_id,predecessor_revision,predecessor_status_id)` FK, explicit null-pair checks; E contiguous revision/terminal checks | Cross-authorization predecessor, gaps, re-admission and terminal append fail closed |
| Immutable admitted approval set | S `approval_manifest` status snapshot; E exact complete link-object-array equality for every status | Late extra links fail; nonempty/separate recorded requester and approver references enforced; eligibility/threshold still requires real verifier |
| Current effective authorization | I:4 `g08_owner_decision_time`; P `execute` | Latest ADMITTED, valid half-open interval, no consumption, bound live execution assertion; no expiry-only mutable flag |
| Fresh post-lock reads / protected time | I lock → authorization/status/assertion/consumption reads → `clock_timestamp`; P lock → load → database-clock port | M2-A global key and READ COMMITTED discipline reused; actual PostgreSQL wait/snapshot behavior unexecuted |
| One-time operation consumption | S:67 `g08_owner_operation_consumptions` operation PK, unique authorization/event/evidence, composite evidence FK; I:89 `g08_stage_owner_consumption` | Same or fresh-key execution rejected after consumption; no automatic replay mutation |
| Immutable execution evidence | S:49 `g08_owner_execution_evidence`; S:79 evidence↔consumption deferred cycle; E exact event/receipt/status/assertion/time/digest/result comparisons | Missing/orphan/cross-operation/inconsistent proof cannot form a valid complete history; references/hashes are not a verified control PASS |
| Bidirectional owner event / receipt completeness | E orphan queries and STRICT lookups for every consumption, plus M2-A checker | Every owner event/receipt requires one matching consumption/evidence chain; every proof requires consumption |
| Authorization audit | Status row, assertion FK, immutable approval manifest, rationale/evidence, actual session/effective role from status primitive | Committed status history is audit; rejected/rolled-back actions do not create success records |
| Execution audit | Immutable evidence/consumption chain to M2-A event/receipt; assertion/verifier/session, authority, technical and fencing references | Result/time/digest agree structurally; source authenticity is a closed external dependency |
| Independently authenticated human operator | S:15 purpose-bound assertion schema; P `OperatorAssertion`, `_operator`; I:116 `g08_verify_owner_trust` | No UID copied from approver/JWT/caller JSON; assertion records are not an identity source; unavailable verifier denies every route |
| Owner admission / revocation / invalidation interfaces | I private `g08_stage_owner_admission` / `g08_stage_owner_status`; I:127 `g08_control_owner_operation`; P coordinator | No ordinary direct admission or business-owner approval-minting permission. Authority policy remains mandatory and closed |
| Execution-time authority | I effective-state function and deferred temporal checks; P separate operator verification, permission and technical/fencing verification stages | An authenticated person or owner approval alone cannot permit execution |
| Controlled writer / reader privileges | S:4–12 bounded roles; S explicit table revokes and checker SELECT policies; I per-function revokes and final schema CREATE revokes | Runtime/identity/owner function roles get no new table writes; owner reader has no direct table access; no role memberships assigned |
| Read-only SECURITY DEFINER checking | E:6 `g08_assert_owner_history`, E:123 trigger wrapper, explicit eight-table unfiltered policy/ownership assertions | Checker owns functions only, has bounded SELECT and private EXECUTE of M2-A checker; no writes/dynamic SQL/exception suppression |
| Revoked/invalidated authority | E rejects terminal status at/before consumption time; I rejects current terminal state; P execution checks | Later terminal status does not erase earlier valid event/receipt. Equality with execution time fails conservatively; no retroactive cancellation guarantee |
| Commit acknowledgement | P operations invoke unchanged `services/g08_transaction_boundary.py:27` `execute_once` | Durable wrapper returned only after COMMIT returns; precommit failure rolls back; unacknowledged commit stays unknown |
| Unknown execution commit / exact replay | P `reconcile`, `_receipt`; I:141 closed receipt reader | Exact original operation/key/canonical bytes/digest/operator/event/result required under CURRENT read permission; absence/conflict stays quarantined |
| Unknown admission/terminal commit | P `reconcile_status`; I:154 closed status reader | Original preallocated status ID/status/predecessor only; never append a fresh transition to resolve uncertainty |
| Concurrent attempts | Global-lock SQL guards and uniqueness; coordinator fake-transaction thread test | One modeled execution commits, second freshly reads consumed state; real PostgreSQL concurrency remains required |
| Unspecified identity/fencing semantics | P:129 `UnavailableOwnerTrust`; I:116 verifier always raises SQLSTATE 55000 | No boolean trust flags, identity success stub, default approver policy, fabricated session binding or technical PASS |

## C. Executed offline verification and limitations

Reproduce from repository root:

```powershell
.venv/Scripts/python.exe scripts/run_m2b_offline_verification.py
```

Result: **98 passed** — 28 preserved M2-A tests and 70 new M2-B cases (64 coordinator cases, six static artifact cases). Four new Python sources parsed successfully; no source hygiene issues. Preservation checks: **100 pre-existing files checked, zero changed**. The fingerprint set includes existing tracked modifications and retained M0/M1/M2-A documents, code, tests and evidence, including M2-A's three staged SQL files. Evidence: `offline/results.xml`, `offline/pytest.log`, `offline/checks.json`, `preservation-baseline.json`, `artifact-manifest.json`. No baseline evidence was overwritten.

Coverage includes valid lifecycle, illegal initial/gapped/stale/duplicate/terminal histories, revoked/invalidated/expired authority, duplicate admission and same/fresh-key replay, operation/person/session/purpose/validity mismatches, unauthorized execution, missing/mismatched evidence, proof/receipt inconsistency rollback, unavailable assurance on all interfaces, rejected boolean/JSON permission responses, competing thread attempts, commit loss before/after server-model commit, receipt/status reconciliation, current read denial and missing/conflicting original outcomes.

The runner constructs an allowlisted child environment, disables dotenv and pytest plugin discovery, and uses the unchanged M1 guard to block network/database construction. No database credentials are copied into the child. Test doubles exist only in tests; no synthetic provider is supplied by the implementation. The fake transaction model proves coordinator call order and state handling against that model, not PostgreSQL isolation or an external identity service.

**No PostgreSQL execution or SQL-parser validation occurred.** No FK/trigger/RLS/role/function behavior on a server is claimed verified. `git diff --check` passed for tracked worktree changes; new-source whitespace/AST checks are recorded separately by the runner. Existing unrelated suites that may connect to databases were not run.

## D. M2-A/M2-B compatibility findings

- All three M2-A staged migrations, the M2-A transaction helper, tests, report and prior evidence remain byte-identical to the preservation baseline. M0/M1 and release guards were preserved.
- M2-B does not change shared human receipt columns, human actor NOT NULL, owner fingerprint version, current/version/event key topology or the global lock key. Existing human execution remains closed by M2-A's unresolved interface.
- M2-B adds four tables and extra checks over four relevant M2-A tables. Its checker composes M2-A's checker rather than replacing its body. Extra checker-only permissive SELECT policies do not replace M2-A's required policies or expose runtime reads. Actual effective catalog privileges still need qualification.
- New admission snapshots freeze complete owner approval-link objects, extending M2-A's receipt approval-ref completeness to the pre-execution authorization lifecycle. The SHA/manifest authority is not inferred from those snapshots.
- Existing owner rows without real admission/assertions/evidence/consumption will fail M2-B's installation check. No ADMITTED status or assurance is silently generated for them. A nonempty target needs an authorized provenance-aware data migration and compatibility review, rather than automatic installation of these blank-schema staged files.
- M2-A's original PostgreSQL fixture intentionally creates owner history without M2-B fields. Run it in the M2-A-only disposable fixture before M2-B installation; it is not a valid post-M2-B fixture. Use the new M2-B fixture after all six migration files. The existing M2-A offline tests pass unchanged.
- The coordinator is a driver-independent boundary, not an installed RPC adapter. `OwnerUnitOfWork.stage_execution` remains an explicit integration port: a future adapter must stage actual current/version/event/receipt AND M2-B proof/consumption in one transaction. The new SQL consumption primitive checks already-staged M2-A outcomes; it does not invent owner mutation semantics, root policy, or an external execution service.
- Python verifies SHA-256 consistency of supplied canonical bytes, not D08 canonicalization correctness. The provider must validate approved bytes and intent semantics. SQL enforces JSONB and immutable linkage, not authenticity of a hex digest.
- The Python result boundary requires an event-ID result envelope for reconciliation. The complete accepted owner result/projection contract remains an M2-C prerequisite; this generic linkage is not a claim that an owner operation or technical control succeeded.

## E. Remaining identity and PostgreSQL dependencies

Retained authority search: inspected the three M2-A migrations and mapping; searched repository filenames (including hidden contract names, excluding Git/dependency/evidence trees) and retained docs for DBR resolutions/status directions. **No identifiable DBR-01 v0.2/v0.3 material was found.** `deploy/staging/NXR-CLOSE-016/G08_GATE_A_CONTRACT_RESOLUTION_V0_2.md` is a different G08 resolution. The available DBR addendum remains v0.1. No missing approved content was reconstructed or labeled accepted. The user directive supplies this batch's implementation authority; historical acceptance labels were preserved.

Precise dependencies:

| Dependency | Retained source / implementation boundary | Required evidence |
|---|---|---|
| Authoritative missing resolution versions | M2-A report authority section; DBR addendum:463–490 | Exact retained v0.2/v0.3 artifacts, or authoritative disposition identifying the actual source, before claiming exact-version conformance |
| Real human authentication + natural-person/session binding | `G08_D02_D03_DATABASE_RESOLUTION_ADDENDUM_V0_1.md:301`, `:325`, `:440`; P `UnavailableOwnerTrust.verify_operator`; I `g08_verify_owner_trust` | Approved provider/source, verifier authority, independently authenticated person identity, session/operation binding, optional Auth UID verification and current assurance |
| Admission/revocation/invalidation/current authority policy | Addendum:325 and :440; candidate A03/A07/A08; P `OwnerTrust.authorize` | Actual validators/operators, eligible requester/approvers/executor, required independence/threshold/lifetime/delegation, authorized terminal-state actors and policy versions. Nonempty references are not that proof |
| Technical execution evidence + succession | Addendum:385–393; candidate A08; P `verify_execution`; S execution-evidence references | Accepted verifier/outcome schema, actual source, freshness and operation/result binding; verified usable replacement before predecessor retirement. Owner approval is insufficient |
| Cross-system fencing / live authority | Addendum:415–418 and :454; P unavailable evidence verifier | Approved Auth/session/invalidation protocol, fence scope/token/expiry/recheck rules and fail-closed outage behavior. Advisory locks serialize participating DB writers only |
| D08 serializer / SHA / mutation binding | Addendum:345–376; candidate C03; canonical-byte and SQL JSONB boundaries | Independent approved vectors, exact serializer/digest and proof that typed mutation/state matches authorized opaque intent, not merely matching receipt JSON |
| D10 current reader/replay rights | Addendum:424–431; candidate C04; I closed status/receipt readers | Actual authorized projections and denial semantics after expiry/revocation; separate mutation versus historical read permission |
| Managed-platform/catalog compatibility | Candidate B05–B08; staged installation/checker functions | Role creation/transfer support, actual ACL/default/inherited/PUBLIC grants and membership paths, policies, all protected invalidators and legacy overload inventory |

All source names in the table are under `deploy/staging/NXR-CLOSE-016/`. Hashes of retained authority inputs are in `artifact-manifest.json`. Terminal-state/action semantics implemented here are the directed ADMITTED→REVOKED/INVALIDATED integrity graph; unresolved actor eligibility was not guessed. Approval-count, bootstrap/recovery, successor and retention policies remain guarded dependencies.

PostgreSQL tests **still required, all NOT RUN**:

1. Parse/install the six staged SQL files on a separately authorized blank disposable PostgreSQL fixture with `auth.users`, required runtime role names, installer role-creation/transfer authority and continuous quiescence. Qualify PL/pgSQL composite assignments, domains, exact FK timing, triggers, effective grants/RLS and checker ownership/visibility. No Supabase SQL or new/external target is authorized by this report.
2. Run `tests/owner_authorization/postgres_qualification.sql` with stop-on-error. It rolls back its data and temporary fixture functions. The installation itself is outside that rollback. It covers admission/terminal lifecycle, bad predecessors, append-only/late-link denial, current terminal/expired/wrong-operator denial, missing/mismatched execution evidence, actual evidence/consumption insertion, replay, later revocation, checker visibility/read-only behavior, runtime denial and unavailable trust denial under the bounded function owner. All fixture identities/hashes/approvals/technical references are explicitly synthetic, not accepted assurance.
3. Provision the explicit committed fixture prerequisites for `postgres_race_session_a.sql` / `postgres_race_session_b.sql`, run concurrently, retain wait and SQLSTATE evidence: B must wait for A's revocation and freshly deny with 42501 after A commits. The script requires custodian-provided assertion/status IDs and never creates a real identity source.
4. Qualify two competing full executions under same/different idempotency keys; only one can consume the operation. Qualify opposite revocation/execution commit orders, expiry while waiting, READ COMMITTED enforcement, old-writer participation and no visible intermediate event/proof/receipt/consumption. The two-session scripts alone are not full execution concurrency qualification.
5. Qualify missing/orphan/cross-operation evidence in both directions and COMMIT-time failure/rollback, `SET CONSTRAINTS` timing, terminal timestamp ordering and all correct-mode receipt checks. Qualify D08/result interoperability, actual proof authenticity and cross-system fences after those adapters exist.
6. Lose the real driver's commit acknowledgement before/after server commit for admission/status/execution. Reconcile the original ID/key through a currently authorized read; never infer permission to retry from absence. Verify adapter atomicity and no external action performed by evidence-verification callbacks.
7. Measure full-history checker/queued-trigger cost on representative histories and inspect complete managed-role/default/inherited/PUBLIC privileges. Privileged DDL that disables triggers or bypasses RLS is outside the bounded-caller guarantee.

## F. Precise M2-C integration and validation prerequisites

1. Preserve the six staged migrations, retained decision files, reports and release guards. Resolve the missing-resolution identity and freeze authoritative policy, evidence/result/projection and target compatibility inputs before asserting exact conformance. Do not reactivate M2-A's ordinary human execution interface as an owner fallback.
2. Supply reviewed real implementations of the three `OwnerTrust` methods. Verify independent human identity and session binding, current authority including admission/terminal-action/D10 policy, D08 canonical intent, actual technical evidence and cross-system fences. Methods must raise on denial/unavailability; boolean/JSON permission responses are rejected. They must verify existing evidence, not perform external mutations inside a database transaction.
3. Implement a single-transaction `OwnerUnitOfWork` adapter. `begin_read_committed` must precede any protected read; global lock key `16002003001` must precede row/scoped locks. `load` must read full checked history/current state after waiting; `decision_time` must come from the protected database clock after fresh reads. Do not use a detached store, stale cached snapshot or client timestamp.
4. Implement the trusted owner current/version/event/receipt mutation wrapper against exact authorized typed semantics. Integrate admission/status assertions with `g08_stage_owner_admission`/`g08_stage_owner_status`, and atomically insert checked outcome/evidence/consumption using `g08_stage_owner_consumption`. Require current authority and independent technical/succession evidence before any write. No intermediate commit; no direct runtime grant to private persistence primitives; execution owner must never mint approvals.
5. Implement exact D10 status/receipt projections and real-driver acknowledgement/quarantine. The current SQL readers deliberately raise; replacing only the trust hook cannot activate them. Admission and terminal-action uncertainty uses original status ID, execution uncertainty uses original operation/key/canonical content. Current read denial, absence or inconsistency must not trigger a mutation retry.
6. Reconcile complete existing-data/writer/overload/catalog and external Auth invalidation coverage. If real owner history already exists, obtain an explicit truthful migration plan; no synthetic ADMITTED/assertion/evidence backfill. Maintain quiescence across installation steps.
7. Obtain separate disposable PostgreSQL qualification authorization and execute E's tests. After code/target evidence is reviewed, any managed-platform installation, service activation, packaging/release change, deployment or Git publication requires its own applicable scope. This report grants none of those actions.

## G. Completion recommendation

**Independently implementable M2-B work is delivered and offline verified.** Close this controlled implementation pass with 98 passing offline tests and preservation evidence. Keep database qualification and the listed real trust/adapter integrations OPEN; do not describe M2-B as operationally accepted, deployable or activated. M0/M1 external qualifications, M2-A qualification and all existing G08/staging/production controls remain unchanged.

PostgreSQL semantics were reviewed against official [constraint-trigger documentation](https://www.postgresql.org/docs/17/sql-createtrigger.html), [READ COMMITTED command snapshots](https://www.postgresql.org/docs/17/transaction-iso.html) and [function ownership/security configuration](https://www.postgresql.org/docs/17/sql-createfunction.html). Documentation review is not PostgreSQL execution evidence.
