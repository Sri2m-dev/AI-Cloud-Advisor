# NXR-DASH-RC-01 controlled staging acceptance

Current decision: **BLOCKED** pending D1-D8, separate hosted access authorization and approved
migration/replay packaging. Production **NO-GO**. Azure Start Discovery **BLOCKED**.
This is an operator checklist for AFTER approvals, not permission to execute hosted steps now.
See [approval register](NXR-DASH-RC-01-approval-register.md). No hosted steps were executed.

For every step record operator, timestamp, target identity, artifact hashes, expected/actual result
and evidence reference. Keep tokens, secrets and retained source contents out of release logs.
Stop on any target ambiguity, production/shared data, failed authorization or missing approval.

| Step | Operator action after authorization | Required evidence / pass condition |
|---|---|---|
| 1. Isolate target | Database/staging owner verifies project ID, endpoint, database, environment inventory and dedicated staging access. Confirm no production credentials, tenant data or shared workload; provision only approved synthetic/test tenant identities. Capture `select current_database(), current_user, inet_server_addr(), version();` on the authorized target. | Target agrees with approved inventory and is isolated non-production. An endpoint name alone is insufficient. STOP if identification or data provenance is uncertain. |
| 2. Migration/replay | Migration owner supplies reviewed ordered migration bundle, hashes, preconditions, full current canonical-chain replay certificate and rollback plan. Check October UUID binding and RC object ordering. | Existing repository manifest is still BLOCKED and cannot be used as execution authority. Do not apply the standalone candidate as a substitute. Separately approve migration execution before installation. |
| 3. Auth UUID/session | Identity owner tests actual signed user sessions against authoritative `users.auth_user_id`/org membership, role policy and revocation rules; include unbound, deleted, expired and revoked cases. | Valid A/B subjects resolve only their own scope. Caller org hints, email, mutable metadata and service-role claims cannot select membership. Preserve sanitized denial evidence. |
| 4. Read/publish privileges | Database/security owner validates approved deployed role matrix, private ownership and function access for anon/authenticated/backend reader/publisher/issuer/attester. Test missing, wrong-operation, revoked and expired capabilities. | Read cannot refresh; publisher cannot issue capabilities/attestations. Direct private-table access denied. The candidate unconditional authority denial must be replaced only by a separately approved implementation, never just removed. |
| 5. Independent source | Evidence owner retains an authorized AWS CUR artifact/version under D2/D8, verifies actual byte digest (csv/gzip convention), parses independently and supplies attestation/reconciliation through approved authority. | Hash/payer/currency/whole-period/count/amount agree with retained bytes. Unknown scale/amount/time, duplicate/replacement or missing evidence blocks certification. No normalized-total backfill. Live AWS retrieval needs separate authorization; do not contact AWS under this checklist alone. |
| 6. Tenant separation | Operator prepares explicit A/B coverage, then exercises A reads/publishes with B identifiers, B reads of A, service-role misuse and current-session revocation. | All foreign/missing-authority operations deny; A publication leaves B pointer/membership/cache unchanged. Record both positive and negative outcomes. |
| 7. Publication | Authorized ingestion/publisher operator ingests the reviewed dataset, independently reconciles, then refreshes with explicit coverage, trigger, request UUID and expected prior generation. Exercise concurrency, same-request retry and failure injection. | Ledger/import/fact membership and pointer commit atomically; receipt is returned only after commit. Retry returns original generation/time; superseded receipt cannot republish. Failed refresh preserves old pointer. Stale same-total mutation blocks reads. |
| 8. Active Executive page | Application owner installs `AwsFinancialReadBackend` through server bootstrap with approved read transport, current tenant verifier, canonical `AwsFinancialReadSelection` reader and lookup of already issued read capabilities. Bind scope/actor from verified context; do not populate from browser session/query fields. Open Executive Command Center as authorized A. | Route pages/executive_command_center.py -> shared/executive_page.py -> panel -> backend read composition -> evidence RPC. Network/DB trace shows read only: no ingestion, refresh, grant issuance or attestation on render. Source, currency/period, coverage, verified total and persisted publication time match envelope. Without bindings/data show NOT_READY/UNKNOWN. |
| 9. Reconcile visible values | Operator compares retained-source independent amounts, each import, every included fact, reconciliation, frozen membership and dashboard total using Decimal/exact numeric. Repeat after a stale mutation and authority revocation. | All IDs/counts/amounts/currency/period agree; actual snapshot_id and persisted generation distinguish observation from publication time. Optional synthetic 12000+8000=20000 remains synthetic evidence. Never claim live billing activation from it. |
| 10. Release evidence/rollback | Release owner captures sanitized RPC envelopes/receipts, membership/digest references, role/session denials, page screenshots, approvals, checksums and test logs. Demonstrate approved rollback. | Disable server backend binding/new use, revoke only approved new entry points through authorized database owner procedure, retain immutable history/source/audit and restore prior approved reader. Do not repoint stale generations to fabricate readiness, drop evidence or change the blocked manifest. Obtain separate release/production activation decision. |

## Local validation (safe to reproduce now)

Run from the repository with the existing virtual environment; no hosted connections are required:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.venv/Scripts/python.exe -m pytest tests/financial_data_fabric/test_nxr_dash_rc_01_composition.py tests/financial_data_fabric/test_nxr_dash_10_adapters.py tests/cur_ingestion/test_aws_financial_import_contribution_verifier.py tests/cur_ingestion/test_aws_financial_ingestion_orchestrator.py tests/contracts/test_nxr_dash_09_contract_draft.py tests/financial_data_fabric/test_pvt003c1_dashboard_and_migration.py tests/executive_experience/test_customer_journey_ux.py -q -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check shared/executive_page.py components/aws_financial_publication.py services/aws_financial_dashboard_adapter.py services/aws_financial_ingestion_composition.py tests/financial_data_fabric/test_nxr_dash_rc_01_composition.py
.venv/Scripts/python.exe -m ruff format --check shared/executive_page.py components/aws_financial_publication.py services/aws_financial_dashboard_adapter.py services/aws_financial_ingestion_composition.py tests/financial_data_fabric/test_nxr_dash_rc_01_composition.py
git diff --check
```

Compile the five Python files in memory (no pyc output) and compare all pre-existing
Git-listed bytes to the RC baseline, excluding only the four authorized composition edits.
No SQL, auth module, repository, CUR engine or migration changes are part of RC-01.
The new test executes the actual active-route function with offline dependencies and real
panel/composition/adapter logic; it does not start Streamlit or contact infrastructure.

Optional PostgreSQL mechanics regression is the existing fresh-cluster harness under separate
operator execution with isolation verified. It is not needed for these Python-only changes.
Do not run that fixture's synthetic authority shim or bootstrap on any hosted/shared database.

## Evidence to close the gate

Attach signed D1-D8 decisions, separate target/access/migration authorizations, canonical-chain
replay certification, target-server mechanics results, real hosted Auth/RLS role/session results,
independent retained-source proof, A/B positive/negative acceptance and active-page evidence.
Until all are present the gate stays BLOCKED, regardless of local tests.

Exact next action: security/identity and database owners resolve D1/D3/D7 by signing the trusted
issuer/session verification and read-role/transaction-transport contract for an identified isolated
staging target; record evidence in the approval register before any hosted test authorization.

## Recorded RC-01 local result

2026-10-15: **194 focused offline tests passed**, including 15 new RC composition/route
cases and 179 prior focused cases. Ruff lint and format checks PASS (five Python files);
Python compile-in-memory, new-file whitespace and git diff --check PASS.
No PostgreSQL, hosted Supabase, AWS/Azure, application server or deployment was executed.
Prior 13 PostgreSQL tests were not rerun; they remain NXR-DASH-10 historical evidence.

Preservation PASS: 2104 pre-existing Git-listed files unchanged. Only the four allowed
composition files changed; one new focused test file and the two allowed RC documents added.
HEAD and 12 ahead / 0 behind unchanged. Preserved raw-byte SHA-256:

- SQL candidate: `aa3782070a06ac2bfa8dcdf04bf3bfd3f2a9276f0835d2320c73f0488562e499`
- BLOCKED manifest: `7b9fc74bad5e2f712d5259c42d344fc9dd17b41662ed4d4882837e4b4a3bcddb`

Local composition closure: PASS for the backend-owned, verified, read-only wiring and
fail-closed panel. Hosted dependency installation and real identity/evidence validation:
NOT EXECUTED. D1-D8: PENDING. Controlled staging activation: **BLOCKED**.
