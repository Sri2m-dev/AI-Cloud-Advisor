# WP-001 — Release Baseline and Compatibility Harness

Status: Implemented; pending Program G review

Baseline: `v1.2.0-data-fabric` (`0a4ab32f4ad431a22ec3ae11cc962cc54c5b15e2`)

Delivery owner: Srikanth Mudaliar

Increment: Increment 1

Branch: `feature/wp-001-release-compatibility-harness`

## Authorized scope

WP-001 freezes the released public canonical Data Fabric contract surface as a deterministic golden fixture and provides an automated drift check. It does not add registry, identity, connector, graph, decision, UI, schema, migration, Supabase, or runtime behavior.

## Compatibility boundary

The v1.2.0 fixture covers the ten exports in `data_fabric.contracts`:

- public export order;
- dataclass field order and resolved type labels;
- required, literal-default, and factory-default classifications;
- frozen and slotted contract characteristics;
- enum values and ordering;
- defining module names;
- exact baseline tag and commit identity.

The initial policy is intentionally strict: any drift fails the gate. A future compatible extension still requires an authorized work package, architecture/contract review, fixture regeneration, and evidence explaining the compatibility decision.

## Usage

Check the current contracts:

```powershell
python scripts/check_data_fabric_compatibility.py
```

After an explicitly approved baseline change only:

```powershell
python scripts/check_data_fabric_compatibility.py --write
```

`--write` is a maintenance mechanism, not approval to change the contract.

## Definition of Ready

- G1 architecture baseline ratified.
- G2 release and `v1.2.0-data-fabric` baseline completed.
- G3 authorized the P5 work-package catalog.
- Exact WP-001 scope, owner, increment, baseline, and branch recorded.
- No dependency beyond the released baseline remains unresolved.

## Acceptance criteria

- The golden fixture is deterministic and identifies the exact released baseline.
- The harness returns success for unchanged v1.2.0 contracts.
- Contract drift produces a non-zero result and a precise path.
- The check runs without secrets, network access, databases, or external services.
- Existing compile, lint, full-test, P3, integration-gating, and dependency checks remain green.
- No later work-package capability or runtime behavior is introduced.

## Required evidence

- committed golden fixture and compatibility checker;
- focused automated harness tests;
- exact full-suite and P3-gate results;
- dependency, compile/import, lint, and secret-free integration results;
- clean diff and worktree review;
- hosted CI result for the review commit;
- Program G architecture-conformance and merge decisions.

## Definition of Done

WP-001 is complete only after all acceptance criteria pass, the branch is reviewed through Program G, hosted CI succeeds, evidence is recorded, and merge approval is issued. Completion of implementation alone does not close the work package or authorize WP-002.

## Architecture conformance

The harness protects the released P3 canonical contract boundary. It does not reinterpret source authority, canonical stewardship, tenant ownership, graph projection, Decision Intelligence, Enterprise Memory, or AI authority. No ADR or architectural invariant is modified.
