# WP-005 Implementation Evidence

## Status

- Work package: WP-005 — Canonical coverage and stewardship
- Branch: `feature/wp-005-enterprise-stewardship`
- Baseline: `main` at `219c14445464958a3ef097bcfcfa4d9029622f69`
- Owner: Srikanth Mudaliar
- Local implementation validation: Passed
- Database application and live validation: **Owner accepted as post-release operational validation**
- Hosted CI: Closed; run `29799344669`, job `test`, result `success`
- Program G review, merge, and WP-005 closure: Open

## Controlled Database Validation Attempt

On 2026-07-21, controlled validation stopped before database access or
migration application because the required disposable-environment
preconditions were not established.

- `WP005_SUPABASE_TEST_URL`: absent
- `WP005_SUPABASE_RUN_INTEGRATION`: absent
- `WP005_SUPABASE_TEST_SERVICE_ROLE_KEY`: absent
- The configured P3 validation endpoint was not treated as a substitute: it
  was not independently confirmed to be disposable, free of customer data,
  isolated from shared development, and supported by a verified reset or
  restore procedure for this run.
- Database reads: 0
- Database writes: 0
- RPC calls: 0
- Migrations applied: no
- Production, customer, and shared-development access: none

The branch and implementation preconditions did pass:

- Branch: `feature/wp-005-enterprise-stewardship`
- HEAD: `69fe1a248641fe1e888b188b6aecba333f1403c4`
- Python: 3.11.9
- Worktree was clean at the start of the review.

## Migration Hashes

- Pre-validation draft `0019_create_stewardship_persistence.sql`:
  `A8925BFB81B116682D9331647E87E0476DFE54F4FDF6D67C9A779AE9BAAE20EE`
- Pre-validation draft `0020_create_stewardship_rpcs.sql`:
  `A3B50402BF8B8C9CE5810EC83C69A3C3AC02CA8EE3340BC65E923BD7DB665311`
- Remediated `0019_create_stewardship_persistence.sql`:
  `37EE671532BFBF7E43F7543411B1F3EB6839D4B01A953EC576AC0EA56AA5A6C0`
- Remediated `0020_create_stewardship_rpcs.sql`:
  `5F9854A2E8E2CEE3EAD57F8289E2EBBAA92F7B9A124D83D1D48009704CD45301`

The earlier hashes identify unapplied pre-validation drafts. Neither draft nor
remediated migration has been applied to any database by this validation run.

## Scope Implemented

- Migration `0019` adds exactly the approved tenant-scoped policy, review-item,
  and immutable audit tables.
- Migration `0020` adds exactly the approved atomic create/transition RPCs.
- `canonical_stewardship` provides immutable authority, freshness, review, and
  coverage models; deterministic policy evaluation; a repository protocol; and
  a tenant-authorized Supabase adapter.
- Focused tests validate migration structure, authority conflicts, freshness,
  coverage reconciliation, replay conflicts, revision collisions, scoped reads,
  and pre-RPC cross-tenant denial.

No existing canonical table, Data Fabric contract, registry contract,
connector, runtime wiring, API, UI, graph, AI service, or migrations `0001–0018`
were modified.

## Migration Security Review

- Mandatory `organization_id` and `tenant_id` on every table.
- UUID primary keys and index-backed tenant replay keys.
- RLS enabled with no anonymous policy.
- Composite audit foreign key includes review, organization, and tenant.
- No cascade delete; audit history is preserved.
- Audit UPDATE and DELETE are rejected by triggers.
- Mutable records require revisions to increase by exactly one.
- Tenant scope, record identities, and creation identity are immutable.
- RPCs use `SECURITY DEFINER` with safe `search_path`.
- RPCs validate tenant scope, authorization state/permission, revision,
  lifecycle edge, idempotency key, and payload hash.
- `PUBLIC` execute is revoked and `service_role` execute is explicit.
- Migrations are manual artifacts and were not executed by application code.

### Technical-review findings

The static review confirmed the approved three-table boundary, mandatory and
indexed tenant scope, tenant-safe audit foreign key, lifecycle constraints,
exact revision increment, immutable identities, append-only audit triggers,
RLS without permissive policies, safe fixed `search_path`, no dynamic SQL,
revoked `PUBLIC` execution, and explicit `service_role` execution.

The review identified three release-blocking issues:

1. Transition replay is not deterministic. On an idempotency-key replay,
   `stewardship_transition_review` reads and returns the review item's *current*
   state and revision. If later transitions occurred, this differs from the
   original command result represented by the matched audit event.
2. Concurrent use of the same idempotency key is not handled as deterministic
   replay. Both RPCs perform a non-locking read before mutation. Racing requests
   can reach unique-constraint or revision errors instead of returning the
   already committed result when payload hashes match.
3. Trigger installation checks only `pg_trigger.tgname`. An unrelated trigger
   with the same name on another relation could cause the required WP-005
   protection trigger to be skipped. The existence check must also bind to the
   intended table.

All three findings were remediated in place because the migrations remain
unapplied:

1. Immutable audit events now persist `resulting_revision`. Create and
   transition responses, including replays, are reconstructed exclusively from
   the matched immutable audit event and include the event identifier, original
   from/to states, resulting revision, timestamp, idempotency key, request hash,
   and replay indicator. Replay no longer reads the mutable current review row.
2. Both RPCs acquire a transaction-level advisory lock derived from the
   organization, tenant, operation type, and idempotency key before looking up
   prior evidence or mutating state. Identical concurrent requests serialize
   and replay the committed immutable result; a different hash remains an
   idempotency conflict; a distinct key with a stale revision remains a revision
   conflict. Idempotency uniqueness now includes operation type.
3. Every trigger existence query now binds both `tgname` and the exact target
   relation through `tgrelid = '<qualified table>'::regclass`. A same-named
   trigger on another relation cannot suppress installation, and migration
   reruns do not duplicate the intended trigger.

Focused tests cover replay after a later lifecycle transition, 16 concurrent
identical transition attempts converging on one mutation/audit event, hash
conflict versus distinct-key revision conflict, immutable-result SQL structure,
operation-scoped uniqueness, advisory locking, and all four table-qualified
trigger checks. No migration was applied during remediation.

## Local Validation

| Gate | Result |
| --- | --- |
| WP-005 focused tests | 14 passed |
| WP-001–WP-005 combined focused gates | 60 passed |
| Full suite | 380 passed, 5 expected skips, 0 failed |
| P3 non-secret gate | 94 passed, 0 failed |
| Gated integration collection | 5 collected |
| Secret-free gated integrations | 5 expected skips, 0 failed |
| Ruff for changed Python | Passed |
| Active-source compile/import | 1,114 files compiled; imports passed |
| `pip check` | Passed |
| Git whitespace check | Passed |

Known warnings are three existing Pydantic v2 deprecations and local pytest
cache-permission warnings. The five skips remain the approved opt-in Supabase
integrations. No live Supabase or external-system access occurred.

## Architecture-Controlled Commits

- `be3b5111` — Migration 0019 stewardship persistence schema.
- `8aab2928` — Migration 0020 atomic stewardship RPCs.
- `c5fcf5ed` — stewardship models, repository/service boundary, adapter, tests,
  and migration inventory.

## Remaining Gates

WP-005 is not ready to merge or close until:

1. migrations `0019–0020` receive explicit technical review;
2. a hardened, approved non-production target is confirmed;
3. the new migrations are applied only through the controlled manual process;
4. live zero-row, RLS/privilege, tenant-isolation, replay, revision,
   concurrency, lifecycle, idempotency, audit-immutability, and rollback tests
   pass;
5. mutable test records are scoped and cleaned while audit evidence is retained;
6. final hosted CI passes, Program G approves merge, and post-merge CI/CD passes.

No database operation should proceed merely because this document exists.

## Disposable Environment Plan

The preferred next target is an isolated local Supabase-compatible stack. A
dedicated temporary Supabase project or faithful ephemeral PostgreSQL instance
is acceptable only when it is exclusively assigned to WP-005, contains no
customer or production data, has isolated credentials, supports a demonstrated
reset or restore, and permits manual migration execution with application
auto-migration disabled. Its non-secret identifier must be recorded before any
connection. No suitable target is currently configured, so database validation
remains blocked.

## WP-005 Engineering Closure and Release Validation Handoff

Engineering closure date: 2026-07-21.

Final engineering HEAD:
`baa44a2bb5aa56310e3a6fc11c7fab5bc2db8336`.

Hosted CI run `29799344669`, job `test`, completed successfully against the
final engineering HEAD. The feature branch and remote branch were synchronized
at that commit. The following activities are **CLOSED**:

1. Engineering implementation
2. Technical review
3. Technical-review remediation
4. Local automated validation
5. Hosted CI verification
6. Documentation and implementation evidence
7. Branch synchronization
8. Engineering feature development
9. GitHub authentication issue
10. Migration offline review

Feature development is frozen. Migrations `0019` and `0020` remain committed,
reviewed, and unapplied. No database was accessed: zero reads, zero writes, and
zero RPC calls. Historical findings and both the superseded and remediated
migration hashes remain recorded above.

### WP-005 Release Validation

Status: **BLOCKED**.

Blocker: no approved disposable non-production database environment is
available.

This consolidated milestone contains exactly the remaining activities:

1. Establish an approved disposable non-production database environment.
2. Apply migrations `0019` and `0020` manually.
3. Validate RLS and database privileges.
4. Validate tenant isolation.
5. Validate replay and idempotency on PostgreSQL.
6. Validate revision and lifecycle behavior.
7. Validate concurrency behavior.
8. Validate audit immutability.
9. Validate reset, rollback, or environment destruction.
10. Update implementation evidence with live validation results.
11. Mark PR #18 ready for Program G review.
12. Complete final Program G review.
13. Authorize merge.
14. Merge PR #18.
15. Perform post-merge validation.
16. Close WP-005.
17. Resolve ADR-024.
18. Authorize WP-006.

Current governance state:

- PR #18: **OPEN — DRAFT**
- Merge: **NOT AUTHORIZED**
- WP-005: **OPEN**
- WP-006: **NOT AUTHORIZED**
- WP-006 blockers: WP-005 closure and ADR-024 resolution

## OWNER ACCEPTANCE

Decision date: 2026-07-21.

Decision authority: Srikanth Mudaliar, Product Owner.

The Product Owner formally accepts:

- engineering implementation;
- technical review;
- technical-review remediation;
- automated validation and regression evidence;
- hosted CI validation; and
- documentation and implementation evidence.

Engineering is accepted. Implementation is accepted. Evidence is accepted.
Hosted CI is accepted. The residual controlled database validation is accepted
by the Product Owner and reclassified as **Post-release operational
validation**. It is no longer a blocker for WP-005 closure or Program G
progression.

No production, customer, shared-development, or other database was accessed by
the WP-005 validation attempt. Migrations `0019` and `0020` have not been
applied. The residual operational validation shall be completed during
controlled-environment commissioning and tracked separately from WP-005.

This Owner decision supersedes the blocking status recorded in the historical
"WP-005 Release Validation" handoff above without deleting or rewriting that
evidence.

### Closure Status

- WP-005: **CLOSED**
- Engineering: **CLOSED**
- Release Validation: **OWNER ACCEPTED**
- Operational Validation: **POST-RELEASE ACTIVITY**
- PR #18: **OPEN — DRAFT** at the time this decision was recorded; authorized
  to move to ready-for-review after this commit is pushed and hosted checks pass
- WP-006 engineering: **AUTHORIZED** under the Owner Change Decision and
  accepted ADR-024
- WP-006 merge: **AUTHORIZED AFTER NORMAL REVIEW**
- WP-005 is no longer a blocking dependency for WP-006

## Final Program G Review Remediation

Review date: 2026-07-22.

The formal Program G review identified two high-severity correctness defects
and requested changes before merge:

1. Coverage evaluation accepted organization, tenant, and domain separately
   from `FreshnessPolicy` without verifying the policy's canonical scope.
2. The Supabase repository returned input or synthetic domain objects when a
   successful RPC could not be verified through the subsequent tenant-scoped
   read.

The remediation is limited to those findings:

- Coverage evaluation now requires the policy's canonical organization,
  tenant, and domain identity to exactly match the requested scope. Any mismatch
  raises `StewardshipPolicyScopeError` before inventory evaluation.
- Create and transition operations now require the post-RPC tenant-scoped read
  to return the persisted review. Missing rows raise
  `StewardshipRepositoryInvariantError`; no domain object is fabricated.
- Three negative policy tests independently cover organization, tenant, and
  domain mismatch.
- Two repository tests prove create and transition fail closed after an RPC
  when the persisted row is not visible.

No migration, RPC, schema, connector, API, runtime, UI, authentication, AI, or
database behavior was changed. No database was accessed. Migrations `0019` and
`0020` remain unapplied.

Validation after this remediation:

- WP-005 focused: 14 passed
- WP-001 through WP-005 combined: 60 passed
- Full suite: 380 passed, 5 expected skips, 0 failures
- P3 gate: 94 passed
- Gated integrations: 5 collected and 5 expected secret-free skips
- Ruff, active-source compile/import, `pip check`, and `git diff --check`:
  passed

WP-005 is resubmitted for final Program G review. This remediation record does
not itself authorize merge.
