# NXR-DASH-RC-02 local acceptance evidence

2026-10-15. Target scope: **fresh disposable local PostgreSQL only**.
Accountable owner: **Nexora Product Owner**, as explicitly stated in this conversation.
Production **NO-GO**. Live AWS/Azure and hosted Supabase access are not authorized.

## Product-owner authorization record

The attached RC-02 request authorizes controlled validation only after environment,
authority and migration prerequisites are verified. The owner's subsequent clarification
narrows the target to a fresh local PostgreSQL environment with synthetic tenants A/B,
CUR ingestion, canonical evidence, role/RLS checks, publication and Executive integration.
It explicitly excludes hosted access, production credentials, blocked-chain execution and
unresolved privileged authority activation. This approval governs product scope and local
test execution; it does not delegate identity/security/database governance authority.

No prior cluster was reused. No hosted target was selected or contacted. The initial
asynchronous staging-target question was resolved by the owner's local-only instruction.

## Changes

- Modified `tests/financial_data_fabric/test_nxr_dash_10_postgres.py`: strengthen the fresh
  cluster preflight with owned temporary-path checks and SQL verification of connection
  role/session role, loopback server address and initial database before fixture writes.
- Added `tests/financial_data_fabric/test_nxr_dash_rc_02_local_acceptance.py`: execute the
  actual active Executive workspace function against real local canonical RPC/repository/
  adapter/composition logic; test read-only rendering, tenant denial and stale evidence.
- Added this acceptance record. No application, SQL contract, migration, auth, CUR engine,
  repository, deployment configuration or prior approval-register changes were necessary.

## Isolation, database objects and authority boundaries

Installed PostgreSQL 18.3 binaries are used to initdb a new randomly named temporary
cluster, with a new random bootstrap role and ephemeral 127.0.0.1 listener. The harness
checks the resolved data_directory against the directory it just created, current_user
and session_user against that role, server address against loopback, the initial postgres
database inventory and absence of public application relations before any fixture SQL.
Each test case creates a random database. Only synthetic fixture data is introduced.
The bootstrap role is a disposable test superuser, not a production/service-role identity.
Cluster shutdown and temporary-directory removal demonstrate recreation/rollback capability.
No database URL, environment credentials or existing PostgreSQL service is accepted.

Only minimal synthetic Auth/users/organizations, six canonical table CREATE definitions
extracted from the CUR foundation, and the standalone financial SQL candidate are installed.
This is **not** execution or certification of the existing BLOCKED migration chain.
The six new evidence/publication tables are source_attestation, operation_authorization_grant,
projection_generation (ledger/receipt), published_generation_pointer,
published_import_membership and published_fact_membership. Both versioned RPCs are exercised.
All six evidence tables retain forced RLS and runtime privilege revokes.

Positive mechanics tests reuse the existing, explicitly test-only authority shim, synthetic
capability fixtures and independent CSV-byte parser inside the disposable database only.
Those mocks are not approved issuers/attesters, trusted runtime grants or real JWT verification.
The application SQL candidate remains unconditionally default-deny; no unresolved runtime
privileges/authorities are activated. A separate default-deny test uses the unmodified hook.
Local role-denial checks cover anon/authenticated/service_role direct access and RPC execution.
Hosted Auth/JWT/session behavior and hosted RLS allow policies are **NOT EXECUTED**.

## Source-to-dashboard acceptance

Synthetic source 1 USD 12,000 + source 2 USD 8,000 -> existing ingestion engine -> real
canonical facts -> independent fixture-byte reconciliation/attestation -> tenant generation
and immutable membership -> persisted refresh receipt -> versioned evidence read -> real
repository/adapter/verifier -> backend-owned composition -> actual Executive route function.

Ready assertions cover tenant A, USD, July 2026 period, two imports/two facts, USD 20,000,
complete coverage and timestamp equality to the persisted receipt. The active route uses
injected synthetic identity/UI and doubles for unrelated services; AWS reads and financial
computation execute against PostgreSQL. No Streamlit browser/server or hosted login is claimed.

A read capability fixture is prepared before rendering. Row counts before/after rendering
prove no new grants, attestations, facts or generations. Recorded page RPC traffic contains
only the evidence read. Browser tenant/grant hints are ignored. Tenant B gets NOT_READY/UNKNOWN;
a same-total canonical hash mutation also gets NOT_READY/UNKNOWN on the next render.
Disabling backend composition returns NOT_READY. No demo or legacy financial fallback occurs.
Existing database cases also cover concurrent publication, idempotency, superseded retries,
immutable/complete membership, source mismatch, unknown mappings and rollback after pointer update.

## D1-D8 authority assessment

| Decision | Is product-owner scope approval sufficient? | Independent authority still required / implementation result |
|---|---|---|
| D1 issuer | No, only local synthetic mocking is authorized. | Identity + security owner must approve/provide the real issuer; default denial remains. |
| D2 source attester | No. | Data evidence + security owner must approve independent retained-source/parse/reconciliation authority; only synthetic bytes are independently parsed here. |
| D3 read privilege | No. | Database + security owner must approve reader role/wrapper privileges; unapproved runtime roles still deny. |
| D4 publish privilege | No. | Database + security owner must approve publisher isolation/permissions; only fixture bootstrap executes mechanics. |
| D5 writer coordination | Sufficient to test local mechanics, not approve deployed writer changes. | Ingestion + database owner must approve all-writer protocol and target-server behavior; local concurrency/rollback assertions test candidate behavior. |
| D6 dashboard behavior | Sufficient for product/local acceptance direction; not for hosted authority bindings. | Dashboard/contract owner must approve target-specific backend configuration after identity/read prerequisites. Local backend-owned route is tested. |
| D7 session/transaction | Sufficient to run local transaction tests, not define real identity/session policy. | Identity + database owner must approve real session revocation and hosted transport; local read-only snapshot/serializable mechanics are exercised. |
| D8 retention/audit | Sufficient for disposable synthetic test cleanup, not organizational evidence retention policy. | Data governance + security owner must approve real retention/audit/deletion; candidate immutable history remains intact. |

D1-D8 runtime/security decisions remain **PENDING**. Product/local execution authorization
is recorded separately; no decision has been silently converted to APPROVED.

## Preservation

Branch `program/nexora-production-activation`, HEAD
`3b4a1100d86ef05dd915cf1734a2c4fa6581c299`, recorded upstream 12 ahead / 0 behind without fetch.
Initial 2111 Git-listed files aggregate raw-byte SHA-256:
`cb7cee657861d810495f8340661c4b25f9d02962f5955202ab6f1fbd114479f1`.
Algorithm: sorted path-to-raw-byte-SHA-256 map, compact sorted JSON UTF-8, then SHA-256.
Only the existing disposable test harness is modified; unrelated work and all application,
SQL, manifest and prior RC artifacts remain unchanged. No Git writes or cloud access.

## Exact hosted prerequisite

Hosted staging is outside the owner's clarified scope. The next prerequisite is a separate
owner-authorized hosted target handoff: non-secret project/database identifier, accountable
database owner, isolation/no-production-data/recreation evidence, connection-role approval,
approved migration dependency/replay package and applicable identity/security/data authority
references. Do not access hosted infrastructure or substitute the local fixture shim before
that handoff is authorized and verified. LOCAL DATABASE PASS cannot imply HOSTED STAGING PASS.

## Final execution results

**LOCAL DATABASE PASS. HOSTED STAGING BLOCKED / NOT EXECUTED. Overall RC-02: PARTIAL.**
Final runs: **14 PostgreSQL integration tests passed** (57.58 seconds), including the new
active-route acceptance; **194 focused application tests passed**. No final test failures.
Ruff lint and format checks PASS across eight relevant Python files; Python syntax,
whitespace, git diff --check and preservation checks PASS.
An initial strengthened isolation probe expected a bare IPv4 value from an inet text cast;
using host(inet_server_addr()) corrected its CIDR formatting before fixture SQL.

Final fresh local cluster identities (PostgreSQL 18.3, loopback only):

| Test use | Temporary directory suffix | System identifier | Port | Verified bootstrap role |
|---|---|---|---|---|
| Database mechanics suite | nxr-dash10-synthetic-wf0dtl9i/cluster | 7696722979144617156 | 59712 | nxr_test_0776cda9d7e34023b3b09a192d72fa58 |
| Active-route database acceptance | nxr-dash10-synthetic-rabz94td/cluster | 7696723174790933156 | 63584 | nxr_test_d6966efc33eb4a06aec308acde89d73c |

Both directories were created under the local user's AppData/Local/Temp, verified empty
before canonical fixture installation, shut down and removed by the fixture lifecycle.
Final preservation: **2110 pre-existing Git-listed files unchanged**, one authorized local
harness modification and the two additions listed above. HEAD/divergence and BLOCKED
manifest remain unchanged. No runtime authority, hosted target or production object activated.

Reproduce local database acceptance (requires local PostgreSQL 18 binaries and the same
explicit permission to create fresh disposable clusters):

```powershell
$env:NXR_DASH10_LOCAL_PG='1'
$env:PYTHONDONTWRITEBYTECODE='1'
.venv/Scripts/python.exe -m pytest tests/financial_data_fabric/test_nxr_dash_10_postgres.py tests/financial_data_fabric/test_nxr_dash_rc_02_local_acceptance.py -q -s -p no:cacheprovider
```
