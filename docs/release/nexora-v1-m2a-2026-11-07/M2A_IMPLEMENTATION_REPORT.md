# NEXORA M2-A implementation and offline verification

7 November 2026, Asia/Calcutta. Branch: `program/nexora-production-activation`.

Disposition: **independent DBR-01 integrity implementation delivered; M2-A full closure blocked**. These are actual SQL and Python implementation artifacts with reproducible offline verification. No PostgreSQL parser/server execution, Supabase SQL, database connection, restoration access, deployment, commit, tag, push or release-guard change occurred. No technical acceptance is asserted.

## A. Implemented artifacts

Staged SQL migrations, in dependency order:

1. `database/contracts/g08_m2a/S020_integrity.sql`: 11 public tables, domains, indexes, composite/deferred references, role creation, forced RLS and explicit runtime privilege denial.
2. `database/contracts/g08_m2a/A020A_enforcement.sql`: global transaction lock, complete-history read-only SECURITY DEFINER checker, deferred triggers on all 11 tables, append-only/current-provenance guards, and closed execution interface.
3. `database/contracts/g08_m2a/A020A_private_writer.sql`: atomic authenticated persistence primitive, fresh post-lock reads, post-read decision time, one-time request/key enforcement, version/event/link/receipt insertion and current update. It is SECURITY INVOKER, receives no grants, and supplies no authorization. The identity function owner cannot invoke it or write the tables. Its returned UUID means staged, never committed.

The existing repository has staged SQL in `database/contracts`; these files deliberately remain outside the automatic Supabase migration queue. No CLI migration, remote diff or installation was performed. Existing objects cause CREATE to fail rather than being silently replaced. A target with existing G08/shared-receipt objects needs a separately reviewed compatibility migration; this package does not overwrite them or restrict an existing shared namespace. Installation must keep all writers quiescent across the three transactions. Managed-role creation, ownership transfer and final privileges need qualification.

Application boundary: `services/g08_transaction_boundary.py` supplies driver-independent commit acknowledgement and exact authorized reconciliation. It opens no connection, imports no database SDK and is not wired to runtime routes. The explicit release packaging allowlist remains unchanged; this helper is consequently not activated or packaged by this work.

Tests: `tests/database_integrity/test_g08_offline.py`, `postgres_qualification.sql`, and two `postgres_lock_session_*.sql` files. Runner: `scripts/run_m2a_offline_verification.py`. PostgreSQL fixtures are synthetic structural evidence only and are UNEXECUTED.

## Authority and compatibility limits

Repository-wide Markdown search found DBR-01/DBR-02 in the retained **v0.1 database addendum**, not DBR-01 resolution v0.2/v0.3. The available v0.2 file is `deploy/staging/NXR-CLOSE-016/G08_GATE_A_CONTRACT_RESOLUTION_V0_2.md`; it is a different G08 document. No missing resolution was reconstructed or declared approved. This user instruction authorizes implementation; the retained documents' historical proposed/pending labels were not rewritten.

Retained basis:

- `G08_D02_D03_IMPLEMENTATION_CONTRACT_CANDIDATE_V0_1.md`: A01–A06 physical history; A07–A08 authority dependencies; B01–B07 role/lock protocol; C01–C05 fingerprints, replay and errors.
- `G08_D02_D03_DATABASE_RESOLUTION_ADDENDUM_V0_1.md`: A3 deferred topology/checker; B3–B5 separate owner records; B8 trust-boundary restrictions.
- `G08_GATE_B2_DECISION_CLOSURE_REGISTER_V0_1.md`: preserved PO-D10 and DD decisions.

All paths above are under `deploy/staging/NXR-CLOSE-016/`. `artifact-manifest.json` records SHA-256 of these inputs and delivered source artifacts. PO-D10 independence is enforced as recorded UID/person-reference consistency; those strings are never treated as identity verification. A nonempty approval set is an integrity minimum, not a selected policy threshold. DD-01/DD-02/DD-03 owner workflows remain closed pending trusted admission, independent-approval policy and successor verification. Owner approval supplies no technical-control PASS.

## B. Requirement-to-code mapping

Line references are to the delivered files, with function/constraint names for stable lookup. S = `S020_integrity.sql`, E = `A020A_enforcement.sql`, W = `A020A_private_writer.sql` in `database/contracts/g08_m2a/`.

| Requirement | Exact implementation | Status / verification limit |
|---|---|---|
| Current administrative snapshot | S:63 `g08_identity_administrators` | Implemented; retained Auth FK, intervals, provenance |
| Immutable complete versions | S:72 `g08_identity_administrator_versions`; E `g08_append_only` triggers | Implemented |
| Immutable events / requests | S:20,107; E trigger inventory | Implemented; trusted request admission closed |
| Approvals / withdrawals / event links | S:41,56,149; composite request/intent/policy FK | Implemented; eligibility/admission not inferred |
| Shared human receipts | S:154; human actor NOT NULL, scoped key uniqueness | Implemented for newly created table; no existing namespaces changed |
| Owner authorizations / approval links / receipts | S:83,100,166 | Structural implementation; admission/execution closed |
| Immutable execution evidence | E `g08_assert_identity_history`: exact human canonical/result and recorded approval set; S receipt/link immutability | Human structural evidence implemented; owner result/status/technical-evidence semantics unresolved |
| Composite keys and mutual FK timing | S:133–148 `g08_current_version_fk`, `g08_origin_event_fk`, `g08_version_event_fk`, `g08_event_version_fk` | Four deferred constraints; predecessor/authorizer FKs immediate |
| Initial history / exact predecessor | E checker: ordered `v.revision<>n`, revision 1/origin grant, `before_revision=n-1` | Implemented; gaps, orphan/missing counterparts fail |
| Current/version equality | E checker: `to_jsonb(p)-'event_id'` equals full current row, `n=c.revision` | Implemented; latest equals current, older versions remain historical |
| Immutable provenance | E checker compares subject/start/origin/evidence for every version; `g08_guard_current_update` | Implemented |
| Legal append-only transitions | E checker initial/revise/revoke branches; current guard forbids post-revocation updates | Implemented; expired/revoked predecessors cannot reactivate |
| Bidirectional human receipt completeness | E orphan query, STRICT receipt lookup, mode checks, full result/canonical equality | Implemented |
| Exact approval sets / late extra links | E sorted `ids`, exact human canonical and result arrays | Implemented; duplicate PK and empty set rejection |
| Owner approval set completeness | S `approval_refs` integrity projection; E exact comparison with admitted link refs | Implemented projection; manifest hash authenticity/serialization remains external |
| Owner receipt completeness | E STRICT mode-aware lookup, cross-mode exclusion, authorization/operator/operation/canonical linkage | Structural; complete owner result and verified UID attestation require DBR-02 |
| Withdrawal integrity | Immutable withdrawal FK/uniqueness; E tests withdrawal time against historical decision | Implemented; later withdrawal does not erase valid history; withdrawal admission closed |
| Revocation integrity | E exact `revoked_at=occurred_at`, unchanged expiry, no subsequent revision | Implemented; cross-system denial/root-count authorization remains blocked |
| Explicit database role boundaries | S checker/identity NOLOGIN/NOBYPASSRLS roles, table revokes and explicit SELECT policy; E final schema CREATE revoke | Implemented SQL; actual grants/memberships need catalog qualification |
| Read-only SECURITY DEFINER checker | E:19 `g08_assert_identity_history`, E:184 trigger wrapper; bounded SELECT-only owner | Implemented; no writes/dynamic SQL/locks in checker |
| Checker full visibility | E catalog assertions require all 11 forced-RLS tables, explicit true SELECT policy, separate table owner, no restrictive SELECT policies | Fail closed; runtime visibility/read-only behavior unexecuted |
| Deferred consistency on every touched table | E explicit 11-table `g08_complete_history` constraint-trigger inventory | Full global history scanned; correctness prioritized; cost qualification pending |
| Global transaction lock / READ COMMITTED | E:6 `g08_lock_identity_history`; BEFORE STATEMENT trigger precedes row locks; W first command | Implemented on new objects only; all existing invalidators still require inventory/integration |
| Fresh protected state after lock | W separate checker/current/key/request queries after lock acquisition | Implemented command order; waiting/snapshot behavior needs PostgreSQL test |
| Protected decision time | W `clock_timestamp()` after protected reads; receipt/event/revocation share timestamp, UTC result projection | Implemented primitive; production clock/interface qualification pending |
| Commit acknowledgement | `services/g08_transaction_boundary.py:27` `execute_once` | Mock-tested; result published only after commit returns |
| Unknown commit / replay | Boundary:43 `reconcile_exact`; W denies consumed request and existing key without mutation | Mock-tested; no blind retry/new key; missing/conflicting receipt stays unknown |
| Fail-closed incomplete history | E STRICT lookups, orphan checks, no exception suppression; boundary incomplete/conflicting receipt checks | Implemented; PostgreSQL error/commit rollback unverified |
| Controlled write interfaces | E:245 unresolved dependency throws; E:253 ordinary executor has no runtime grant; W private structural primitive has no grant | Closed safely; production authorization/admission/wrapper intentionally incomplete |
| DBR-02 integration | S operation uniqueness, parent ref, immutable manifests; E mode-specific linkage; separate unresolved dependency | Status history/current authority/operator/evidence adapters remain open; no minted assurance |

## C. Executed verification

Command:

```powershell
.venv/Scripts/python.exe scripts/run_m2a_offline_verification.py --output-dir docs/release/nexora-v1-m2a-2026-11-07/offline
```

Result: **28 passed**. `offline/results.xml` and `offline/pytest.log` are the recorded output. Test types: static artifact assertions plus mocked transaction/reconciliation tests. Sanitized allowlisted child environment; dotenv disabled; existing `scripts.m1_offline_guard` blocks sockets/database/Supabase clients. No database credentials copied to the child. No test here proves PostgreSQL execution.

Python AST parsing passed for the three new Python sources without application imports. Additional source hygiene results are in `offline/source-checks.json`. Existing M0/M1 files, release guards and migrations were not edited; all implementation files are additions. Existing dirty worktree changes were preserved. Broader application suites were not executed because unrelated tests may open databases or external services.

## D. PostgreSQL-backed tests still required

Every PostgreSQL test remains **NOT RUN**. Even SQL syntax, PL/pgSQL composite assignments, role ownership transfer, constraint firing and target compatibility need real qualification. There is no SQL parser PASS in this package.

Under separately authorized disposable PostgreSQL scope, custodian must provision a blank fixture with `auth.users(id)` and `anon/authenticated/service_role` roles, an installer permitted to create roles/transfer function ownership, no application traffic and no inherited runtime paths. Do not run this on production, restoration projects, Supabase or any new/external target without its authorization. Apply the three staged files in order with stop-on-error; ensure no traffic between steps. Then execute `tests/database_integrity/postgres_qualification.sql` with stop-on-error. Its fixture data/negative writes roll back. Role/schema installation is outside that rollback and requires a disposable database/cluster lifecycle.

The supplied fixture covers valid bootstrap + human grant/revise/revoke, invalid revision, missing/duplicate approval input, duplicate/late-extra links, orphan receipt, immutable mutation, later/backdated withdrawals, replay/consumption, post-revocation append, checker restrictive-policy visibility/read-only tests and direct runtime SELECT/INSERT/EXECUTE denial. Fixture owner evidence/hashes are deliberately synthetic and test no identity/digest authenticity.

Run the supplied A/B lock-session scripts concurrently to verify mutual exclusion and transaction release. Additionally qualify:

- Two real competing mutations and opposite orders of revocation versus execution; first commit wins, later authority read denies appropriately.
- Authority/approval expiry during lock waits; refresh membership/org/identity state before the decision time; non-READ-COMMITTED denial; canonical row-lock ordering in integrated writers.
- Failed deferred checks at COMMIT, `SET CONSTRAINTS` timing, atomic rollback of every missing/extra version/event/link/receipt and no visible intermediate history to another session.
- Owner/shared cross-mode receipt substitution, missing owner receipts, missing/inconsistent technical evidence, stale status, consumed-operation fresh-key replay and successor verification. Owner execution cannot be tested as authorized until DBR-02 adapters exist.
- Client disconnect immediately before/after server commit; separately authorized exact receipt reconciliation; current denial and absence must prevent automatic retry.
- Actual managed-role attributes, ownership, membership, column/default/PUBLIC/inherited privileges, RLS policies, old overloads and all root invalidators. Checker must own no table and receive no writes. Restrictive/removed policies must fail closed.
- Approved serializer/SHA vectors, UTC/result compatibility, retention/read projection and shared-receipt namespace migration on the actual accepted catalog.
- Full-history checker cost for realistic histories and queued triggers; every touched row currently invokes a global scan. No scalability claim.

## E–F. DBR-02 dependencies and remaining blockers

1. **Missing retained resolution versions**: supplied repository contains no identified DBR-01 v0.2/v0.3 resolution. Freeze those authoritative inputs before asserting exact approved-version conformance. Available addendum labels and open questions are at `G08_D02_D03_DATABASE_RESOLUTION_ADDENDUM_V0_1.md:465` and `:482`.
2. **Identity, approval policy and current authority**: candidate A03/A07/A08/B02 at `G08_D02_D03_IMPLEMENTATION_CONTRACT_CANDIDATE_V0_1.md:147`, `:250`, `:276`, `:346`. Requires actual natural-person assurance, eligibility/threshold/delegation, validity policy and live membership/org/verification projections. Blocked explicitly by E:245, not caller JSON or inferred UID separation.
3. **Owner admission/status/consumption**: addendum B3–B5 at `:280`, `:331`, `:360`. Requires authenticated operation/session/person binding, authorization status history and current status verifier, one-time consumption keyed by owner operation under the same lock, and exact manifest policy. S event/receipt UNIQUE owner operation supplies structural one-time linkage; it does not establish current authorization or revocation status. No status rows or successful verification responses were fabricated.
4. **Technical execution evidence**: addendum `:380` succession verification and candidate A08. An authorization/approval cannot prove a technical check passed. Need immutable accepted evidence schema, verifier/source, operation/result binding and failure semantics. Human receipt evidence exists; generic technical-control and owner result semantics remain unimplemented rather than invented (E owner branch comment).
5. **Canonicalization and digest**: candidate C03 at `:513`; owner version shape addendum B5. SQL enforces canonical JSONB equality/linkage and digest format, but does not claim that a 64-character hash proves approved canonical bytes. D08 vectors and qualified digest implementation must be supplied to the trusted writer.
6. **Read/reconciliation rights**: candidate C04 at `:537`, addendum B8 at `:423`. D10 must authorize current receipt access. The Python boundary requires an injected authorized reader and grants no entitlement; no public read RPC is installed.
7. **All-writer/target integration**: candidate B05–B08 at `:395`. No exact live overload/catalog/invalidator inventory or platform privilege proof is available. New tables are guarded; existing profile/org/Auth invalidators have not been altered by assumption. No production path invokes this package.
8. **PostgreSQL qualification and operational activation**: all D tests above. M0/M1 external qualifications and all existing G08/release controls remain open as previously recorded. No target authorization was inferred from “continue and close it.”

## G. M2-A recommendation

Close this **controlled implementation/offline-verification pass** with delivered artifacts. **Do not mark M2-A fully complete or activate the writer**. Recommend review of the independent integrity implementation, then completion against the missing frozen resolution inputs and approved trust adapters, followed by separately authorized PostgreSQL qualification. The private persistence primitive is actual implementation, but no approved production mutation path is claimed. Gate A/B2, staging and production dispositions remain unchanged.

## H. Next M2-B implementation instructions

1. Retain all M0/M1/M2-A additions and guard settings. Freeze the exact missing DBR resolutions, final policy interfaces and target catalog compatibility plan; resolve discrepancies before changing physical contracts.
2. Implement separate trusted human request/approval/withdrawal admission. Derive authenticated actors from the approved session channel; establish verified person mappings and policy validity. Do not grant the execution owner approval-minting rights.
3. Implement immutable owner authorization-status history and current verification adapter, session-bound operator verification, manifest validator and one-time consumption. Only separately authorized owner procedures may admit/execute; no human UID copied from an approver or service credential.
4. Define/implement immutable technical execution evidence with exact accepted operation, verifier, outcome and succession linkage. Require usable verified replacement before predecessor retirement; bootstrap/recovery retain independent natural-person requirements. Reject incomplete evidence without writing a success receipt.
5. Implement approved D08 canonical serializer/digest with independent vectors, live authority/root-count/scope checks and D10 authorized receipt/replay reads. Replace the unresolved dependency only as those real adapters become available. Add the narrow wrapper grants/column policies last; never grant the private primitive directly to runtime.
6. Bring every protected invalidator under the same global lock/READ COMMITTED/fresh-read protocol. Keep the lock before row locks; capture one protected decision time; couple event/version/links/receipt/status-consumption atomically. Integrate commit acknowledgement/quarantine with a reviewed real driver adapter; no automatic mutation retry on unknown commit.
7. Under separate environment authorization, qualify D on disposable PostgreSQL, then separately assess managed-platform/catalog compatibility. Retain SQLSTATE/results/concurrency/disconnect evidence and review effective privileges. No hosted SQL, deployment, commit/tag/push or release-guard changes are authorized by these instructions alone.

PostgreSQL reference used for implementation review: [READ COMMITTED command snapshots](https://www.postgresql.org/docs/current/transaction-iso.html) and [function security configuration](https://www.postgresql.org/docs/current/sql-createfunction.html). Documentation consultation is not database qualification.
