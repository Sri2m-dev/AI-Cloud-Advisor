# WP-003 — Contract and Event Governance Toolkit

Status: Implemented; pending Program G review

Baseline: `main` at `aac2be0a569e4c353e43e9899ff110318de7fc12`

Released baseline: `v1.2.0-data-fabric`

Branch: `feature/wp-003-contract-event-governance`

Delivery owner: Srikanth Mudaliar

Increment: Increment 0 — Governed baseline

## Outcome

WP-003 adds an inert governance toolkit for public contracts and events. It provides strict semantic versions, declarative provider field schemas, payload validation, consumer requirements, compatibility classification, deprecation lead-time rules, and an executable registry gate.

It does not modify existing event producers, consumers, Data Fabric contracts, schemas, migrations, connectors, runtime wiring, or application behavior.

## Compatibility policy

| Change | Minimum version change |
|---|---|
| No structural change | None or patch when metadata changes |
| Optional field added | Minor |
| Enum value added | Minor |
| Required field added | Major |
| Field removed | Major |
| Field type changed | Major |
| Optional field becomes required | Major |
| Enum value removed | Major |

Manifest changes without a version increment fail. Provider ownership changes require separate governance and cannot be assessed as ordinary compatibility.

## Deprecation policy

A deprecation notice must identify a present field, replacement, introduction version, and removal version. Removal must remain open until a later major version. Publishing a notice does not itself remove or alter the field.

## Provider/consumer gate

`governance/manifests.json` registers initial governance descriptions for the existing Enterprise Correlation and Workflow Execution event shapes plus their named consumers. The descriptions do not change those runtime events.

Run the gate with:

```powershell
python scripts/check_contract_event_governance.py
```

The gate fails for invalid schemas, duplicate provider identities, missing providers, unmet minimum versions, missing consumer fields, incompatible field types, or invalid deprecations.

## Architecture conformance

The toolkit governs compatibility without defining new canonical enterprise entities, changing source authority, or creating an event runtime. Event transport, delivery, persistence, retries, and orchestration remain outside WP-003.

## Acceptance criteria

- Semantic versions are strict and deterministic.
- Provider schemas validate required fields, types, and enums.
- Breaking changes require a major version.
- Compatible extensions require the correct minor version.
- Consumers verify provider identity, minimum version, fields, and types.
- Deprecations preserve a major-version migration window.
- The committed registry passes an offline executable gate.
- WP-001 compatibility, WP-002 authorization, full regression, and P3 gates remain green.
- Hosted CI passes before Program G review.
