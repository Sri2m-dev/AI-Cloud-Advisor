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


## E8.1.4 Connector Normalization Framework

E8.1.4 introduces the canonical enterprise normalization layer. Vendor connectors should not publish provider-specific payloads directly to downstream intelligence systems. They should normalize into canonical enterprise records first.

### Package Structure

```text
connector_normalization/
    __init__.py
    canonical_models.py
    normalizer.py
    registry.py
    validation.py
    publisher.py
```

### Canonical Enterprise Models

The normalization layer defines canonical records for:

- Cloud resources
- Applications
- Technologies
- Business services
- Business capabilities
- Business units
- Identities
- Vendors
- Cost records
- Recommendations
- Risks
- Incidents
- Changes
- Licenses
- Contracts

### Normalization Flow

```text
Extract Raw Data
  -> Normalize
  -> Canonical Enterprise Record
  -> Validate
  -> Publish
```

### Validation Rules

The first validation layer checks:

- Required fields
- Identifier uniqueness
- Timestamp validity
- Currency normalization
- Tag normalization
- Provider metadata presence

Validation failures are standardized so they can later feed connector health, audit, and operations dashboards.

### Publisher Abstraction

The `CanonicalPublisher` interface is storage-agnostic. Future implementations can target Supabase, PostgreSQL, Kafka, Azure Event Hub, AWS Kinesis, files, or a data lake without changing connector normalization contracts.

### Normalizer Registry

The `NormalizerRegistry` maps provider/source payloads to reusable canonical normalizers. Multiple providers can share the same normalizer when their target canonical model is equivalent.


## E8.1.5 Data Fabric Publisher and Persistence Layer

E8.1.5 introduces a persistence layer for canonical records. This still does not implement production vendor connectors; it defines the storage-agnostic persistence pipeline that connector output will use.

### Package Structure

```text
connector_persistence/
    __init__.py
    repository.py
    publisher.py
    transaction.py
    batch.py
    deduplication.py
    metadata.py
    adapters/
        __init__.py
        memory.py
        supabase.py
```

### Core Responsibilities

- Save and upsert canonical records
- Batch canonical record persistence
- Detect duplicate records
- Track persistence metadata and lineage
- Support transaction lifecycle contracts
- Bridge `CanonicalPublisher` to repository-backed persistence
- Provide memory and Supabase adapter seams

### Canonical Repository Operations

- `save()`
- `save_batch()`
- `upsert()`
- `exists()`
- `delete()`
- `find()`
- `list_records()`

### Deduplication Strategies

- Primary key
- Natural key
- Hash
- External ID
- Composite key

### Persistence Metadata

Persistence metadata tracks:

- Connector
- Provider
- Sync time
- Batch ID
- Correlation ID
- Source system
- Version
- Schema version

### Adapter Strategy

The first adapters are:

- `MemoryCanonicalRepository` for smoke tests and local validation
- `SupabaseCanonicalRepository` as the future E8.2 Data Fabric seam

Future adapters can target PostgreSQL, Kafka, Azure Event Hub, AWS Kinesis, Parquet, Iceberg, Delta Lake, or other enterprise data platforms.


## E8.1.6 Authentication and Secret Management Framework

E8.1.6 introduces a provider-agnostic authentication layer. Connectors should declare what authentication they require; the authentication framework resolves and validates credentials, acquires an auth context, and caches tokens when appropriate.

### Package Structure

```text
connector_auth/
    __init__.py
    auth_manager.py
    providers.py
    credentials.py
    token_cache.py
    oauth.py
    api_key.py
    access_key.py
    certificate.py
    validator.py
```

### Supported Authentication Types

- AWS Access Key
- AWS Assume Role
- Azure Service Principal
- Azure Managed Identity
- OAuth2 Client Credentials
- OAuth2 Authorization Code
- API Key
- Bearer Token
- Basic Authentication
- Certificate Authentication
- Anonymous Authentication for tests

### Initial Secret Providers

- Environment variables
- In-memory provider
- Local key/value configuration provider

Future providers can support AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, Google Secret Manager, Kubernetes Secrets, and other enterprise secret stores.

### Authentication Flow

```text
Resolve Secret Reference
  -> Load Credentials
  -> Validate
  -> Acquire Token or Auth Context
  -> Cache Token
  -> Return Auth Context
```

### Token Cache

The token cache is in-memory, expiration-aware, and thread-safe. It is intentionally provider-independent so future OAuth, cloud, and enterprise identity providers can share the same cache contract.


## E8.1.7 Scheduling, Triggering, and Connector Orchestration

E8.1.7 adds the operational orchestration layer that controls when and how connectors run.

### Package Structure

```text
connector_orchestration/
    __init__.py
    scheduler.py
    trigger.py
    workflow.py
    dependency.py
    retry.py
    queue.py
    coordinator.py
```

### Core Capabilities

- Manual, scheduled, webhook, API, dependency-complete, startup, event, and on-demand triggers
- Workflow steps with dependencies
- Dependency manager for prerequisite completion
- Queue states: waiting, running, completed, failed, cancelled, retrying
- Retry strategies: immediate, linear, exponential backoff, circuit breaker
- Coordinator as a single orchestration entry point

### Standard Operational Flow

```text
Trigger
  -> Queue
  -> Dependency Check
  -> Coordinator
  -> Execution Engine
  -> Runtime State
  -> Health Snapshot
  -> Run Log
  -> Retry or Complete
```

This keeps scheduling and orchestration concerns in the platform instead of inside provider-specific connectors.

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








## E8.1.8 Connector Observability and Telemetry

E8.1.8 adds an observability layer for connector operations. This remains framework-only and does not depend on a production telemetry backend or vendor connector implementation.

### Package Structure

```text
connector_observability/
    __init__.py
    metrics.py
    telemetry.py
    tracing.py
    events.py
    dashboard.py
    alerts.py
    audit.py
```

### Core Capabilities

- Metrics collection for executions, success/failure rates, duration, record counts, retries, and queue depth.
- Structured telemetry events for lifecycle milestones such as connector started, authentication completed, extraction completed, publish completed, succeeded, and failed.
- Trace correlation with execution-level correlation IDs and lifecycle spans.
- Audit events for connector registration, enablement, scheduling, manual execution, authentication failures, validation failures, publish failures, and execution outcomes.
- Alert rule evaluation for consecutive failures, expired authentication, queue backlog, duration thresholds, low health score, and missing successful sync within SLA.
- Dashboard-ready operations snapshots for future Connector Operations UI.

### Runtime Integration

The observability layer is optional and plugs into the existing runtime hook contract through `ConnectorObservabilityHooks`. Provider-specific connectors do not own telemetry flow. The runtime can attach hooks that emit metrics, telemetry, traces, lifecycle events, and audit records without changing connector implementations.

### Operational Model

```text
Connector Execution
  -> Metrics Collector
  -> Telemetry Events
  -> Trace Correlation
  -> Audit Log
  -> Alert Rules
  -> Dashboard Snapshot
```

### Scope

This phase intentionally avoids external telemetry systems. Future releases can route the same contracts to OpenTelemetry, Datadog, Azure Monitor, CloudWatch, Splunk, Kafka, or a persistent audit ledger without changing connector lifecycle contracts.
