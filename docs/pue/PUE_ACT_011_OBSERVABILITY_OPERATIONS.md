# ACT-011 Observability, Audit, and Operations

## Architecture

ACT-011 extends the existing ACT-009 lifecycle repository; it does not create a
second durable audit database. `GovernedOperationsService` writes authoritative,
scope-bound events to that repository and also sends bounded operational events
to `InMemoryOperationalTelemetry`. Telemetry is process-local and is never the
audit authority. Provenance remains in its existing domain models and is linked
from events by fingerprints/references rather than being treated as audit.

Every event uses the bounded `GovernedEventType`, `FailureClass`, and `ReasonCode`
vocabularies. Events carry organization, tenant, optional prospect/analysis,
permitted actor/role, correlation ID, safe references, outcome, severity, reason,
duration, and redacted attributes. SYSTEM is written only to the lifecycle audit
envelope when no authenticated actor exists; the event payload retains a null
actor and does not fabricate a user.

## Audit policy

Mapping overrides, reconciliation decisions, execution authorization, purge,
Kill Switch and activation changes, and security denials require durable audit.
Those operations fail closed if their audit write fails. Reads and ordinary
telemetry do not fail because telemetry or an optional audit write is unavailable.
Corrections are new events. Historical lifecycle audit rows remain append-only.

Audit queries require an operations, auditor, client-admin, or super-admin role
and always require a complete lifecycle scope. Event type, actor, evidence,
correlation, and time filters are applied only within that scope. Demo events use
their own tenant/scope and mode and therefore cannot enter production counters or
queries.

## Privacy and diagnostics

Raw rows, prompts, payloads, credentials, passwords, tokens, API/encryption keys,
connection strings, authenticated database URLs, and bytes are redacted. Free
text is bounded. Migration diagnostics expose a backend identity and schema
version, never a database path or URL. Client errors are mapped to governance,
permission, unavailable, or internal classes; unexpected failures include an
`NX-...` support reference derived from the correlation ID, never a traceback or
database identifier.

Health separates liveness (process running) from readiness (all required governed
dependencies available). Standard probes cover runtime, lifecycle persistence,
schema/migration, audit, canonical registry, Universal Evidence composition, and
Ask. An enabled Kill Switch means live, degraded, and not ready for governed
execution without deleting evidence.

## Retention and deployment

`OperationsRetentionPolicy` defaults durable audit retention to 2,555 days and
process-local telemetry to 1,000 events. Deployments may configure both values.
ACT-011 intentionally installs no destructive scheduler: lifecycle purge and
retention scheduling remain explicit deployment operations and must use the
existing audited lifecycle workflow.

The in-memory telemetry abstraction is deliberately exporter-neutral. A future
deployment may export its counters/events to the platform logging or metrics
backend without changing the authoritative audit contract.

## Production instrumentation inventory

`DurableRuntimeComposition` owns the shared operations dependency and injects it
into semantic governance, normalization/capability, measurement, materialization,
reconciliation, Ask, activation, and lifecycle operations. Upload admission takes
the same dependency explicitly because it precedes durable runtime construction.

| Production boundary | ACT-011 classification |
| --- | --- |
| Upload admission/profile | Instrumented telemetry |
| Semantic confirm/reject/override | Instrumented durable audit; fail-closed |
| Normalization/capability | Instrumented telemetry |
| Authorization and measurement | Instrumented audit plus telemetry |
| Entity materialization | Instrumented telemetry; replay-aware |
| Reconciliation decisions | Instrumented durable audit; bindings telemetry |
| Ask Nexora | Instrumented correlated telemetry; prompt body excluded |
| Activation/Kill Switch | Instrumented durable audit; fail-closed |
| Lifecycle purge | Instrumented durable audit; fail-closed |
| Scope rejection | Instrumented durable security audit |

Legacy pilot counters and activation audit remain `COMPATIBILITY / STILL_REQUIRED`
for frozen ACT-003 through ACT-010 callers. They are not used by ACT-011 operations
status or structured counters and therefore are not double-counted. The ACT-011
event stream is authoritative for new operational metrics and audit queries.
Removal of compatibility sinks is deferred until all callers migrate through the
durable composition root.

Mandatory mutation events are recorded with phase `AUTHORIZED` before the domain
mutation begins. This makes audit failure fail closed without pretending that the
operations layer owns the domain transaction. Telemetry-only exporter failures are
swallowed after event construction and cannot make a safe domain operation fail.
