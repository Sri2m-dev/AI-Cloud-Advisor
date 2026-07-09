# ADR-007: Universal Connector Framework

Status: Accepted - E8.1 Complete
Date: 2026-07-05
Last Updated: 2026-07-07
Program: E8.1 Universal Connector Framework

## Context

Nexora Enterprise Foundation v1.0.0 established the consumption layer: certified workspaces, Business Architecture, Enterprise Financial Model, Knowledge Graph, Technology Digital Twin, Shared Platform Framework, and release engineering.

The next platform limitation is ingestion. Adding each source system directly to dashboards or domain services would create bespoke integrations, duplicated authentication logic, inconsistent sync behavior, and brittle data lineage.

## Decision

Introduce a Universal Connector Framework as the standard ingestion architecture for enterprise systems.

The E8.1 implementation defines the connector control plane, runtime, canonical
models, authentication and secret contracts, orchestration, observability, and
cloud runtime adapter seams:

- `connectors/`
- `connector_sdk/`
- `connector_registry/`
- `connector_scheduler/`
- `connector_health/`
- `connector_secrets/`
- `connector_logs/`
- `connector_runtime/`
- `connector_auth/`
- `connector_normalization/`
- `connector_persistence/`
- `connector_orchestration/`
- `connector_observability/`
- `connector_migration/`
- `connector_adapters/`

The first cloud foundation includes AWS, Azure, and GCP runtime adapter seams.
They support discovery-only and dry-run execution through the E8 runtime while
keeping full production sync disabled by default.

## Core Contracts

The framework defines:

- `BaseConnector`
- `ConnectorMetadata`
- `ConnectorAuthConfig`
- `ConnectorSyncResult`
- `ConnectorHealthStatus`
- `ConnectorRecord`
- `ConnectorSyncState`

Standard lifecycle:

```text
authenticate
  -> discover
  -> extract
  -> normalize
  -> validate
  -> publish
  -> sync_full / sync_incremental
```

## Options Considered

1. Build connectors directly into dashboard services.
2. Build one-off connector scripts per provider.
3. Introduce a shared connector SDK and lifecycle contract first.

## Rationale

A contract-first connector platform ensures every future data source follows the same authentication, extraction, normalization, validation, publishing, health, logging, and scheduling model.

This protects the platform from vendor-specific integration sprawl and creates a stable foundation for E8 Data Fabric and AI reasoning.

## Consequences

- New connectors must implement `BaseConnector`.
- Secrets are referenced by `secret_ref`, not stored in connector configs.
- Connector logs and health are first-class platform concepts.
- Full and incremental sync share a common result model.
- Provider-specific logic belongs in concrete connector packages, not the SDK.

## Future Considerations

- Add persistent connector registry storage.
- Add tenant-aware connector enablement.
- Add scheduler persistence and execution workers.
- Add production cloud API extraction behind feature-gated full-sync adapters.
- Add Microsoft 365, ServiceNow, Datadog, GitHub, Salesforce, SAP, and security connectors.
- Publish normalized records into the Enterprise Data Fabric, Knowledge Graph, and Enterprise Financial Model.

## E8.1 Cloud Foundation Completion

E8.1 closes with:

- AWS reference connector and production runtime adapter seam.
- Azure runtime adapter seam with service-principal mapping and secret-reference hardening.
- GCP reference connector and runtime adapter foundation.
- Connector runtime validation for `DISCOVERY_ONLY` and `DRY_RUN`.
- `FULL_SYNC` guarded and disabled by default for all cloud adapter seams.

This creates the merge-ready Universal Connector Framework baseline for
`v1.1.0-universal-connectors`.

