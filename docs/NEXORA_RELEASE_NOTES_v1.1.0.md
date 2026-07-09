# Nexora v1.1.0 Universal Connectors Release Notes

## Overview

Nexora v1.1.0 introduces the Universal Connector Framework, establishing the
enterprise ingestion foundation for cloud, SaaS, ITSM, DevOps, observability,
identity, finance, ERP, security, and future enterprise systems.

This release complements v1.0.0 Enterprise Foundation:

- v1.0.0 certified the user experience, evidence framework, business architecture, and executive/CIO workspaces.
- v1.1.0 standardizes how enterprise data enters Nexora.

## Major Capabilities

### Universal Connector Platform

- Connector SDK
- Connector runtime
- Connector registry
- Execution engine
- Authentication framework
- Secret management
- Canonical models
- Normalization
- Validation
- Persistence and publishing seams
- Orchestration and scheduling
- Retry and queue management
- Observability, telemetry, audit, and health foundations

### Cloud Foundation

#### AWS

- Reference connector
- Legacy onboarding bridge
- Production runtime adapter seam
- Discovery-only and dry-run runtime execution
- Full sync guarded and disabled by default

#### Azure

- Runtime adapter seam
- Service Principal auth mapping
- `client_secret` to `secret_ref` hardening
- Discovery-only and dry-run runtime execution
- Full sync guarded and disabled by default

#### GCP

- Framework-native reference connector
- Runtime adapter foundation
- `project_id`, `service_account_secret_ref`, and `regions` support
- Canonical cloud resource and cost record normalization
- Full sync guarded and disabled by default

## Validation Summary

```text
Compile validation: PASS
AWS runtime smoke: PASS
Azure runtime smoke: PASS
GCP runtime smoke: PASS
Canonical normalization: PASS
Dry-run publishing disabled: PASS
Full-sync guards: PASS
Existing production paths untouched: PASS
```

## Security Notes

- Runtime auth contracts carry secret references, not raw secrets.
- Azure inline `client_secret` values are stripped from runtime metadata.
- GCP direct service-account JSON/key/private-key values are stripped from runtime metadata.
- Full production sync remains disabled by default for all cloud adapter seams.

## Recommended Tag

```text
v1.1.0-universal-connectors
```

## Next Program

```text
E8.2 Enterprise Data Fabric
```
