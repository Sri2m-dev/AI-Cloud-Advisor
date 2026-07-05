# E8 Universal Connector Framework

Status: E8.1.1 architecture and core SDK skeleton
Release Base: v1.0.0-enterprise-foundation

## Vision

The Universal Connector Framework turns Nexora from a consumption-first enterprise platform into an ingestion-ready Enterprise Intelligence Platform.

Connectors should integrate cloud, SaaS, ITSM, DevOps, observability, identity, finance, ERP, and security systems through one lifecycle:

```text
Authenticate
  -> Discover
  -> Extract
  -> Normalize
  -> Validate
  -> Publish
  -> Knowledge Graph / Financial Model / Dashboards
```

## Goals

- Standardize connector implementation.
- Separate provider-specific logic from platform ingestion contracts.
- Support full sync and incremental sync.
- Establish health, logging, scheduling, and secret-resolution contracts.
- Prepare for Enterprise Data Fabric normalization in E8.2.

## Non-Goals for E8.1.1

- No new production-grade AWS connector implementation.
- No new production-grade Azure connector implementation.
- No new production-grade Microsoft 365 connector implementation.
- No production scheduler worker.
- No persistent secret vault integration.
- No data fabric publishing implementation.

This phase is contracts and skeleton only.

## Package Structure

```text
connectors/
    __init__.py

connector_sdk/
    __init__.py
    base.py
    models.py

connector_registry/
    __init__.py

connector_scheduler/
    __init__.py

connector_health/
    __init__.py

connector_secrets/
    __init__.py

connector_logs/
    __init__.py
```

## Core SDK Contracts

### BaseConnector

The abstract lifecycle contract every connector must implement.

Required methods:

- `authenticate()`
- `discover()`
- `extract()`
- `normalize()`
- `validate()`
- `publish()`

Standard orchestration methods:

- `sync_full()`
- `sync_incremental()`
- `health()`

### ConnectorMetadata

Describes connector identity and capabilities:

- Connector ID
- Name
- Provider
- Category
- Version
- Supported entities
- Full sync support
- Incremental sync support
- Webhook support

### ConnectorAuthConfig

References authentication configuration without storing secrets directly.

Secret values must be resolved through `connector_secrets` using `secret_ref` or a future vault integration.

### ConnectorSyncResult

Standard sync result for full and incremental sync:

- State
- Start and finish timestamps
- Extracted record count
- Normalized record count
- Published record count
- Errors
- Warnings
- Checkpoint
- Duration

### ConnectorHealthStatus

Standard health payload:

- Status
- Message
- Last success
- Last failure
- Consecutive failures
- Latency
- Metadata

## Platform Layers

### Connector Registry

In-memory registry for connector classes. Future releases can add persistent registration, tenant-level enablement, and package discovery.

### Connector Scheduler

Minimal scheduling contract for identifying due connector jobs. Future releases can add workers, persistence, retries, and distributed execution.

### Connector Health

Health monitor contract for collecting connector health state.

### Connector Secrets

Secret provider abstraction. The initial local provider resolves environment variables only and does not store secrets.

### Connector Logs

Audit/event contract for connector execution events. Future releases can route this to a database, observability stack, or audit ledger.

## Expected E8.1 Flow

```text
Connector SDK
  -> First concrete connector
  -> Normalized connector records
  -> Data Fabric staging
  -> Canonical enterprise model
  -> Knowledge Graph enrichment
  -> Enterprise Financial Model enrichment
  -> Certified workspaces
```

## Initial Connector Candidates

Recommended first production connectors after E8.1.1:

1. AWS
2. Azure
3. Microsoft 365 or ServiceNow

## Validation

E8.1.1 validation requires:

```powershell
python -m py_compile connectors\*.py connector_sdk\*.py connector_registry\*.py connector_scheduler\*.py connector_health\*.py connector_secrets\*.py connector_logs\*.py
```

Expected result:

```text
Universal connector contracts compile successfully.
No new production-grade vendor connector implementation included.
```

