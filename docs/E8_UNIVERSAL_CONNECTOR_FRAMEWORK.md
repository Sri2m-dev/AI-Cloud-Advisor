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


## E8.1.2 Runtime Foundation

E8.1.2 adds the first runtime foundation around the connector SDK. These are still in-memory contracts and do not introduce production vendor connectors.

### Runtime Contracts

- `ConnectorRegistry`
- `RegisteredConnector`
- `ConnectorSyncStateStore`
- `ConnectorRunLog`
- `ConnectorHealthStore`
- `ConnectorSecretReference`
- `ConnectorSchedule`
- `ConnectorRuntimeContext`

### Runtime Capabilities

The framework now exposes common operations:

- `register_connector()`
- `get_connector()`
- `list_connectors()`
- `enable_connector()`
- `disable_connector()`
- `record_sync_state()`
- `get_sync_state()`
- `record_run_log()`
- `list_run_logs()`
- `record_health_snapshot()`
- `get_latest_health()`

### Runtime Scope

These stores are intentionally lightweight and in-memory. Future E8 phases can add persistent backing stores, tenant-aware enablement, execution workers, retries, and queue-based scheduling without changing the connector lifecycle contract.


## E8.1.3 Connector Orchestration Engine

E8.1.3 introduces the connector execution engine. The goal is to make the runtime, not individual connectors, responsible for the standard execution flow.

### New Runtime Components

- `ConnectorExecutionEngine`
- `ConnectorExecutionResult`
- `ConnectorExecutionPipeline`
- `ConnectorExecutionPolicy`
- `ConnectorExecutionHooks`
- `ConnectorExecutionException` hierarchy

### Standard Execution Flow

```text
Load Connector
  -> Resolve Secret
  -> Authenticate
  -> Discover
  -> Extract
  -> Normalize
  -> Validate
  -> Publish
  -> Update Sync State
  -> Health Snapshot
  -> Run Log
```

### Execution Modes

- `FULL_SYNC`
- `INCREMENTAL_SYNC`
- `DISCOVERY_ONLY`
- `VALIDATE_ONLY`
- `DRY_RUN`

### Lifecycle Hooks

The runtime exposes no-op hooks that future observability, governance, AI reasoning, and notification layers can extend:

- `before_authenticate()`
- `after_authenticate()`
- `before_extract()`
- `after_extract()`
- `before_publish()`
- `after_publish()`
- `on_success()`
- `on_failure()`

### Error Model

The runtime defines a consistent exception hierarchy:

```text
ConnectorError
  -> ConnectorAuthenticationError
  -> ConnectorDiscoveryError
  -> ConnectorExtractionError
  -> ConnectorValidationError
  -> ConnectorPublishError
  -> ConnectorRuntimeError
```

### Observability Output

Every execution produces:

- Execution ID
- Connector ID
- Start time
- End time
- Duration
- Execution mode
- Sync state
- Extracted record count
- Normalized record count
- Published record count
- Warnings
- Errors
- Health status
- Checkpoint

This data will later feed Connector Operations, platform health, audit history, and enterprise automation.

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



