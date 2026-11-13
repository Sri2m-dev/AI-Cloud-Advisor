# NEXORA M4-G08 Trusted Execution Qualification

**Isolated G08 transaction qualification: PARTIAL GO.** The operation was
admitted, executed through the canonical PostgreSQL gateway, and reconciled.
Real two-session fencing-revocation serialization, lost-ack reconciliation,
runner-restart durability, expiration denial, and tenant-scope checks passed.
Historical receipt access after D10/owner-authorization expiry remains
unqualified and is currently blocked by the reader's policy-validity checks.

**Authenticated application integration: NO-GO.** The API route is tested only
to its controlled `503` fail-closed boundary; no production provider is wired
and no browser login/execution was performed.

**Production verdict: NO-GO.** This does not accept the proposed D10 policy,
qualify a production identity or D08 provider, or authorize privileged execution.
The application G08 route remains fail-closed and inactive.

## Scope and target

| Item | Observed value |
|---|---|
| Compose project | `nexora-g08-canonical-gateway-qual-20261111-1818` |
| Database container | `nexora-g08-canonical-gateway-qual-20261111-1818-database-1` |
| Container ID | `5891a2f40d7f34bbe337fcea1eb1cba8a468611de915e96ef1c0f8b335c741f0` |
| Database | `nexora_m2c_g08gateway_20261111` |
| PostgreSQL | 17.11 (`server_version_num=170011`) |
| Runtime role | `nxr_g08_qual_runtime`, inheriting the least-privilege gateway executor |
| Host-published database port | None |

The test runner connected over the target's private Docker network. It verified
its database, PostgreSQL version, and login identity before testing. The runtime
role has no direct `SELECT` privilege on `g08_d10_policy_versions`; a direct
query raised PostgreSQL `InsufficientPrivilege`.

## Implemented and exercised path

- D10 scoped security-definer APIs: `g08_d10_gateway_read_bundle`,
  `g08_d10_gateway_is_revoked`, `g08_d10_gateway_assert_current`, and the
  policy, approval, revocation, and fencing append/read functions.
- Atomic admission bootstrap: `g08_gateway_stage_owner_authorization` and
  `g08_gateway_stage_admission`.
- Canonical execution and receipt path: `g08_gateway_execute_owner_operation`
  and `g08_gateway_read_owner_receipt`, with the D13 scoped operation reader.
- Python adapters use scoped D10 functions, the existing owner coordinator and
  unit-of-work transaction, signed operator/D08 evidence checks, transactional
  fencing, and canonical gateway persistence. No parallel writer was added.
- Requester Auth UID is separately bound to its canonical person reference;
  fencing and receipt-reader SQL ambiguities and missing least-privilege helper
  grants are covered by additive corrective candidates.

The live qualification generated independent ephemeral Ed25519 keys for the
synthetic app session, operator, D10 policy authority, two approvers, fencing
authority, and D08 evidence. Public keys were explicitly pinned in the test
verifiers. These keys and identities are qualification-only; they are not a
production trust store or evidence of real independent identity.

The D10 policy record is marked `SYNTHETIC_QUALIFICATION` and applies only to
this isolated database. The requested one/two-approver policy, separation of
duties, and historical receipt access rules remain **PROPOSED — OWNER
ACCEPTANCE REQUIRED**.

## Real PostgreSQL results

The opt-in live test completed against the isolated database:

| Scenario | Result |
|---|---|
| Synthetic D10 policy, independent approvals, and canonical admission | Passed |
| Signed operator, application session, D08 evidence, tenant, and operation binding | Passed |
| Policy revalidation and stale policy rejection | Passed; SQL reported `D10 policy changed before owner execution` |
| Stale fencing generation | Rejected before execution |
| Forged approval signature | Rejected by the pinned synthetic verifier |
| Owner effect, event/evidence result, authorization consumption, and receipt | Committed through the canonical gateway |
| Concurrent duplicate execution | Two separate PostgreSQL sessions; exactly one returned a receipt and the other was denied |
| Receipt after a new database connection | Reconciled to the exact committed receipt and event |
| Sequential duplicate | Denied as consumed |
| Cross-tenant historical receipt read | Denied |
| Cross-organization receipt read | Denied |
| Direct D10 table read by runtime role | Denied |

The test asserted that the receipt event ID matched the D08 execution result,
that the read-after-reconnect receipt equaled the committed receipt, and that
the operation projection was consumed. The live test result was **1 passed**.
No browser, r5 route, production identity, or customer operation was involved.

### Failure-path results added on 2026-11-12

| Requested scenario | Result and evidence |
|---|---|
| Concurrent revocation | **Passed for a resource fencing-token revocation.** One PostgreSQL session inserted the signed revocation and held the D10 authority-row lock. A second execution session was observed blocked by `pg_blocking_pids`; after revocation commit, its old token was denied as revoked. The persisted revocation was then read back; advancing to a new generation allowed the separately authorized operation to proceed. |
| Ambiguous commit | **Passed.** The test wrapper committed on the server and then raised a synthetic lost-ack `OperationalError`. The caller received `CommitOutcomeUnknown`; a competing identical request was denied. Authorized reconciliation on a fresh connection returned the original event/receipt. PostgreSQL inspection found exactly one `g08_identity_administrator_events` row and one `g08_owner_operation_receipts` row for the operation. |
| Restart recovery | **Passed for the disposable runner.** The test-only runner container was restarted (not PostgreSQL); after reconnect, the least-privilege receipt projection returned the exact same event ID. This proves persisted reader projection across runner restart, not database restart recovery. |
| Expired authority and receipt access | **Partial.** An expired signed application session was denied before execution, and transactional D10 revalidation denied a policy at a decision time after its `valid_to`. An expired owner-authorization row was not separately created. Receipt access after expiry is not supported by the current read path: `g08_d10_gateway_read_bundle` rejects expired policy; `g08_gateway_read_owner_receipt` also requires the policy to be current and unexpired. Historical-read-after-expiry policy therefore needs an independently authorized, tenant-scoped receipt entitlement before this criterion can pass. |

The receipt evidence IDs from the latest run are synthetic: authorization
`3a4ae630-8afd-4b3c-b77e-bfc7f27e4446`, operation
`077b377a-96d5-4411-acc7-32caf9c723b9`, event
`179bb9e8-883b-4d74-8c00-a2b49c6b9a06`. These identify isolated test records,
not customer or production data.

## SQL candidate source hashes

D14-D19 were applied to the existing isolated target. D10-D13 were already
present in its qualification baseline; their hashes below identify the current
candidate source, not a claim that those migrations were reapplied in this task.

| Candidate | SHA-256 |
|---|---|
| D10 persistent authority | `49D78871A26BDFEE0482B31AD13F7619417A16FEA470B7F9ADB25314CDA9FECB` |
| D11 trusted owner gateway | `7B588BCB1E7DC3D0B3BC03E3DCA0B49DD6AADC47921E1FE7A4B5455E83512F62` |
| D12 gateway status adapter | `AB9EFF2FAAAF5426DC0062E42A110B904006E944F7D2856EDBF3CCEC9C390F85` |
| D13 scoped owner gateway readers | `35B11A6EB34F7456B22D80D4ED1A5BB2AA7C78E8D98E7EBE74236D01AC0D9D2F` |
| D14 D10 gateway and atomic admission | `6D297ACA301753A0C3F689FCF0F89205D7445A52F3D59623A631F3396F19D4EE` |
| D15 requester identity binding | `B29CD2BF52263EACD170488D5FD648CFB746330C33191ABAAB57A609DCC43FAC` |
| D16 fencing revalidation | `42FD2192E913DC056F372D6237EE13C5BFD7F421366656CD90DC13BDA2B9B586` |
| D17 least-privilege dependencies | `ECB9859FFC1104F194F3F8D0F9C76DC64ABD5130DE7CBAD08532DBA8DE7CC77E` |
| D18 receipt binding timestamp | `99324618ED609D00D1854F21003C41A1FC591B3BFAABCC647B35040131A12560` |
| D19 scoped receipt reader | `46AC82DB0A9BE22B5B82DCA3FDEF85AAF25A070A22EEBA9A7AB40E184A85804A` |

## Source files in this qualification

- SQL candidates D11-D19 under `database/contracts/g08_m2c/candidates/`.
- `repositories/g08_canonical_gateway.py` and
  `repositories/g08_postgres_authority.py`.
- `services/g08_owner_authorization.py` and `services/g08_trust_contract.py`.
- `tests/g08_integration/test_trust_contracts.py` and
  `tests/g08_integration/test_live_synthetic_execution.py`.

These are source and test changes only. No commit, tag, push, public
deployment, schema change to a protected database, or application route
activation was performed.

Files changed by this follow-up:

- `repositories/g08_postgres_authority.py` — classify PostgreSQL `NO_DATA_FOUND`
  from time-bounded D10 policy revalidation as a denied authority decision.
- `tests/g08_integration/test_live_synthetic_execution.py` — real two-session
  fencing-revocation serialization, lost-ack injection/reconciliation,
  expired-session and expired-policy rejection, and organization mismatch.
- This qualification document.

The existing application route was not changed. Its authenticated lifecycle
tests returned `401` without authentication, `403` for a mismatched
organization, and `503` for an authenticated request because G08 production
providers are unavailable.

## Regression results and skipped tests

Focused command:

```text
pytest -q -p no:cacheprovider -rs tests/g08_integration
  tests/owner_authorization tests/database_integrity/test_g08_offline.py
159 passed, 5 skipped
```

The separate real PostgreSQL run above adds **1 passed**. Ruff and Python
compilation passed for the changed G08 implementation and test files.
The authenticated application route suite separately reported **27 passed**.

The five default local skips were:

1. The opt-in live test, because a local run had no explicit isolated runtime
   DSN; it was separately executed against the approved target.
2. Two adapter tests because the test-only `nexora_g08_adapter_test` local
   database was not configured.
3. Two adapter tests because their isolated fixture identifiers were absent.

The latter four tests are
`test_postgres_d10_policy_and_approval_evidence_are_persisted`,
`test_postgres_d10_revalidates_current_policy_approvals_and_revocations`,
`test_postgres_d10_rejects_stale_policy_version`, and
`test_postgres_fencing_generation_is_scope_bound_and_transactional`. Their
relevant current-policy, approval, stale-version, and fencing paths were
exercised by the real live test; they were not run as separate tests because
their fixture guard requires another database identity.

## Remaining qualification limits

Not proven by this run:

- Concurrent authorization/approval revocation (the tested race was a fencing
  token revocation).
- Database restart recovery or injected partial-write rollback inspection.
- Historical receipt access after owner-authorization or policy expiry. The
  current receipt projection explicitly requires a current, unexpired policy.
- A production D10 policy authority, independently authenticated operator
  provider, D08 technical evidence provider, production trust roots, or a
  production application adapter.

## Migration reproducibility and application integration

The current target has no migration-history table. The D10-D19 contract files
were reviewed in dependency order against the existing canonical A021 and
D10-D13 baseline. The candidate order is D10, D11, D12, D13, D14, D15, D16,
D17, D18, D19. D14-D19 are additive guarded candidates; D14 expects empty
D10 policy history, and later candidates replace functions from earlier
contracts. D14 contains explicit schema/auth lookup grants; D17 explicitly
revokes and grants the owner decision-time helper and `auth.users(id)` lookup.
The live privilege audit found no direct SELECT/INSERT/UPDATE/DELETE grants on
the inspected D10, receipt, and effect tables for `nxr_g08_qual_runtime`, and
confirmed the tested gateway functions are SECURITY DEFINER, owned by
`nxr_g08_owner_fn_owner`, use `search_path=pg_catalog`, and are executable by
the runtime role. No undocumented manual grant was needed during this run.

A clean replay of D10-D19 was **not run**: the task authorized only the existing
isolated target and prohibited creating another database; replaying D14 into
the populated qualification target is explicitly guarded against. Thus clean
database reproducibility remains unproven, not failed.

The actual authenticated route in `backend/routes/auth.py` still delegates to
`require_protected_workflow`, which returns a controlled 503 until
independently verified operator, accepted/current D10, D08, execution and
receipt projection providers are configured. This avoids treating application
login or synthetic test keys as production authority. The TestClient route
suite passed its authentication/scope/unavailable assertions; browser login
and authenticated application execution were not run because no production
provider or active G08 route exists.

The G08 implementation/live-test Ruff and compilation checks passed. An
additional Ruff command that included the unchanged
`tests/g08_integration/test_application_workflows.py` reported existing
`I001`/`E501` diagnostics in that file; it was not modified as part of this
task. The route tests themselves passed.

## Environment preservation

The qualification database remained the existing container and project above;
it has no published host port. A read-only Docker inventory compared all 25
containers in the saved protected-resource snapshot with current identities:
**25 present, 0 missing, 0 changed**. This includes the previously qualified
r5/Auth/financial resources. No r4, r5, SQ-DB, Auth gateway, financial-data, or
production resource was modified. The disposable runner was attached only to
the target's private network (no default-bridge attachment), restarted for the
recovery check, then removed. The temporary runtime login was disabled after
the checks; the qualification database remains healthy. The G08 application
route remains inactive.
