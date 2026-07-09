# Nexora v1.1.0 Feature Matrix

Release: v1.1.0-universal-connectors  
Program: P2 - Universal Connector Framework  
Status: Release Candidate  
Purpose: Internal release capability matrix for the Universal Connector Framework baseline.

## Capability Matrix

| Capability | Status | Notes |
| --- | --- | --- |
| Universal Connector SDK | Complete | Base connector contracts and metadata models are established. |
| Runtime Engine | Complete | Standard execution engine and policy-driven runtime are implemented. |
| Connector Registry | Complete | Connector registration, enablement, lookup, and sync state foundation are available. |
| Authentication Framework | Complete | Provider-neutral auth contracts and credential manager are available. |
| Secret Management | Complete | Secret reference contracts and local/provider abstractions are available. |
| AWS Reference Connector | Complete | Mock-safe AWS reference connector and runtime bridge are implemented. |
| AWS Runtime Adapter | Complete | Production runtime adapter seam preserves existing AWS production path. |
| Azure Runtime Adapter | Complete | Azure runtime adapter seam supports service-principal metadata. |
| Azure Secret Hardening | Complete | Inline `client_secret` metadata is converted to `secret_ref` in E8 runtime auth metadata. |
| GCP Reference Connector | Complete | Framework-native GCP reference connector is implemented. |
| GCP Runtime Adapter | Complete | GCP runtime adapter supports `project_id`, `service_account_secret_ref`, and regions. |
| Canonical Normalization | Complete | Canonical cloud resource and cost record normalization are available. |
| Persistence Framework | Complete | Storage-agnostic persistence and publisher contracts are available. |
| Orchestration | Complete | Queue, trigger, dependency, retry, coordinator, and workflow foundations are available. |
| Scheduling | Complete | Schedule contracts and orchestration scheduler foundation are available. |
| Observability | Complete | Metrics, events, tracing, audit, alerts, health, logs, and dashboard snapshot foundations are available. |
| Runtime Policy Support | Complete | `DISCOVERY_ONLY`, `DRY_RUN`, `VALIDATE_ONLY`, `INCREMENTAL_SYNC`, and guarded `FULL_SYNC` modes are available. |
| FULL_SYNC Guardrail | Complete | AWS, Azure, and GCP production full sync paths are disabled by default. |
| Legacy Cloud Connection Bridge | Complete | Legacy cloud connection records can map into connector registry-compatible payloads. |
| Existing AWS Production Path | Preserved | Existing production AWS sync path remains untouched by the E8 runtime seam. |
| Existing Azure Production Path | Preserved | Existing Azure onboarding and production behavior remain untouched by the E8 runtime seam. |
| Dashboard Changes | None | No dashboards are changed by the Universal Connector Framework release. |
| Documentation | Complete | Framework docs, ADR-007, release notes, release checklist, review, and ADR index are available. |
| Release Validation | Pending | Final validation occurs during E8.1.17 after merge into `main`. |
| Release Tag | Pending | Tag `v1.1.0-universal-connectors` is deferred until post-merge validation passes. |

## Release Boundary

v1.1.0 establishes the Universal Connector Framework baseline. It does not enable broad production cloud sync through the new runtime by default.

Explicit non-goals for this release:

- No E8.2 Enterprise Data Fabric implementation.
- No dashboard changes.
- No schema changes.
- No automatic replacement of existing AWS or Azure production sync paths.
- No unguarded production `FULL_SYNC` execution through the E8 runtime.

## Post-Merge Gate

The following remain pending until E8.1.17:

- Compile validation on merged `main`.
- AWS discovery-only and dry-run validation.
- Azure discovery-only and dry-run validation.
- GCP discovery-only and dry-run validation.
- `FULL_SYNC` guard validation.
- Azure `secret_ref` validation.
- Executive, CIO, and Business Architecture route regression.
- Legacy AWS production path compatibility confirmation.
- Approval/action path cache-safety confirmation.

## Release Recommendation

```text
Status: Release Candidate
PR Readiness: Ready, pending final review
Tag Readiness: Pending E8.1.17 post-merge validation
```
