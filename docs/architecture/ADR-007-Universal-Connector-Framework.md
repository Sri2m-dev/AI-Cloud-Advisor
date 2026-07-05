# ADR-007: Universal Connector Framework

Status: Accepted
Date: 2026-07-05
Program: E8.1.1 Universal Connector Framework Architecture and Core SDK

## Context

Nexora Enterprise Foundation v1.0.0 established the consumption layer: certified workspaces, Business Architecture, Enterprise Financial Model, Knowledge Graph, Technology Digital Twin, Shared Platform Framework, and release engineering.

The next platform limitation is ingestion. Adding each source system directly to dashboards or domain services would create bespoke integrations, duplicated authentication logic, inconsistent sync behavior, and brittle data lineage.

## Decision

Introduce a Universal Connector Framework as the standard ingestion architecture for enterprise systems.

The first E8.1.1 implementation defines contracts and skeleton layers only:

- `connectors/`
- `connector_sdk/`
- `connector_registry/`
- `connector_scheduler/`
- `connector_health/`
- `connector_secrets/`
- `connector_logs/`

No new production-grade AWS, Azure, Microsoft 365, ServiceNow, or other vendor connector implementation is included in this ADR.

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
- Add OAuth, API key, and service-account auth managers.
- Add retry, rate limit, and backoff policies.
- Add scheduler persistence and execution workers.
- Add first production-grade connectors: AWS, Azure, and Microsoft 365 or ServiceNow.
- Publish normalized records into the Enterprise Data Fabric, Knowledge Graph, and Enterprise Financial Model.

