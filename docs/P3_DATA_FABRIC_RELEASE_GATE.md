# P3 Data Fabric Release Gate

## Candidate

- Source branch: `feature/p3-supabase-live-validation`
- Reviewed candidate: `ddb0ed153dbeeee9d8b5e262ca769eaa3e6786d0`
- Target branch: `main`
- Python: 3.11.9
- Supabase project: dedicated `nexora-p3-validation` project, reference `ageubmyosicypqqkdvox`
- Migrations: 0001 through 0018 confirmed pre-applied; none were applied by the release gate

## Validation evidence

- Hardened URL/safety suite: 40/40 passed
- Live Supabase suite: 5/5 passed
- Original focused regression suite: 55/55 passed
- Release-gate non-secret suite after defect correction: 94/94 passed
- Atomic adapter plus persistence foundation defect verification: 39/39 passed
- Integration collection: 5/5 collected
- Secret-free integration execution: 5 expected opt-in skips, 0 failures, 0 unexpected skips
- Compile validation: `python -m compileall -q data_fabric tests/data_fabric` passed

Live validation covered tenant isolation, optimistic concurrency, stale revisions, append-only enforcement, durable idempotency lifecycle/replay, atomic entity and relationship create/update/replay/rollback, evidence creation, and scoped mutable cleanup. The live checkpoint recorded 13 reads, 13 RPC calls, 23 committed scenario writes, four rejected/rolled-back operations, and five cleanup actions.

## Qualification disposition

### Relationship-version history

Accepted deferred functionality. Migration 0018 deliberately returns `version_created=false` and documents that relationship-version history has no compatible persistence contract yet. This is declared scope, not a failed validation.

### Python 3.11 slotted-dataclass defect

Resolved. `@dataclass(slots=True)` returns a replacement class, while zero-argument `super()` in the generated slotted subclass method retained a closure for the pre-replacement class. Python 3.11 therefore rejected valid `MutableRecord` and `ImmutableRecord` instances; `AppendOnlyRecord` failed transitively. The two affected overrides now call `PersistenceRecord.__post_init__(self)` directly. Signatures, fields, immutability, serialization, and public repository/adapter contracts are unchanged.

## Security and evidence audit

No credential values, temporary database diagnostics, unscoped destructive queries, or local attachment paths are committed. Integration credentials are read only from `P3_SUPABASE_*` variables, represented redacted, and are never sourced from product runtime variables. Ordinary CI has no live credentials: all five integration tests skip through the shared safety gate unless explicitly enabled.

The Data API assumptions are documented in `P3_SUPABASE_LIVE_VALIDATION_CHECKPOINT.md`: schema `USAGE`, narrowly scoped table privileges, and migration-established secured RPC `EXECUTE` privileges. Direct mutation remains unavailable for append-only tables.

Retained evidence is expected. It includes the immutable snapshot `d18b6ccf-71bb-4fcf-80c6-0c338a0572f3`, completed idempotency record `f957a12e-140f-458d-a290-54fd4062a907`, expired idempotency record `5be63383-a5be-4f80-8a21-fb1cc3742086`, and additional uniquely scoped `p3test-` version, lineage, provenance, quality, and durable idempotency rows created by final live runs. Mutable entities were deleted with exact tenant scope and relationships were deactivated according to contract.

## CI reproducibility

`.github/workflows/ci.yml` pins Python 3.11 and now runs the explicit P3 non-secret safety, atomic adapter, persistence, certification, migration/static, compile, and integration-collection checks. Live tests use `config_or_skip()` and do not require service-role credentials on ordinary pushes or pull requests.

The workflow now installs `requirements-dev.txt`; that manifest explicitly supplies `ruff`, `mypy`, and the PostgreSQL test driver used during collection. The P3-specific CI command is reproducible and green. The repository-wide `pytest -q` baseline is not yet green because `tests/services/test_sla_logic.py` imports a missing `services.approval_service.calculate_sla_status` symbol. That service issue is unrelated to Data Fabric and was not changed under this gate.

## Release decision

Release gate recommendation: **CONDITIONAL — P3 APPROVED, REPOSITORY CI BLOCKED**. Both P3 qualifications are dispositioned: relationship history is accepted deferred scope and the Python 3.11 defect is resolved with regression coverage. Merge should wait until the unrelated missing `calculate_sla_status` CI collection blocker is resolved or explicitly accepted by release governance.

Merge and tag remain unauthorized in this gate run. After explicit approval, merge the reviewed release-gate commit into `main`, verify the merge commit and clean worktree, then tag that merge commit as `v1.2.0-data-fabric`. No next implementation phase should begin before the architecture review.

Recommended strategy: a non-fast-forward merge so the reviewed release-candidate boundary remains explicit. Commands are prepared for governance review only and were not executed:

```text
git checkout main
git merge --no-ff feature/p3-supabase-live-validation
git status --short --branch
git tag -a v1.2.0-data-fabric -m "P3 Data Fabric Foundation"
```

The tag command must run only after CI passes on the reviewed merge commit and release governance explicitly authorizes tagging.
