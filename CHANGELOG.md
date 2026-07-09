# Changelog

## v1.1.0-universal-connectors - 2026-07-07

### Added
- Universal Connector Framework for standardized enterprise ingestion across cloud, SaaS, ITSM, DevOps, observability, finance, identity, ERP, and security systems.
- Connector SDK, runtime registry, execution engine, authentication framework, secret management, canonical models, persistence seams, orchestration, scheduling, observability, telemetry, audit, and health foundations.
- AWS reference connector, legacy cloud connection bridge, and AWS production runtime adapter seam.
- Azure runtime adapter seam with service-principal auth mapping and `client_secret` to `secret_ref` hardening.
- GCP framework-native reference connector and production runtime adapter foundation.

### Changed
- Cloud connector architecture now routes provider onboarding toward `connector_registry`, `ConnectorAuthConfig`, `ConnectorRuntimeContext`, and `ConnectorExecutionEngine`.
- Existing AWS and Azure production paths remain preserved while new E8 runtime adapters provide discovery-only and dry-run execution seams.
- GCP onboarding foundation starts natively on the Universal Connector Framework rather than extending legacy connector paths.

### Security
- Azure runtime auth mapping strips inline `client_secret` values from runtime metadata and converts legacy values to deterministic `secret_ref` references.
- GCP runtime auth accepts `service_account_secret_ref` and strips direct service-account JSON/key/private-key values from runtime metadata.
- `FULL_SYNC` remains guarded and disabled by default for AWS, Azure, and GCP production adapter seams.

### Validation
- Connector framework packages compile successfully.
- AWS, Azure, and GCP runtime adapters pass discovery-only execution.
- AWS, Azure, and GCP runtime adapters pass dry-run execution with canonical normalization and zero publishing.
- AWS, Azure, and GCP production full sync paths remain disabled by default.

### Notes
- E8.1 is merge-ready as the Universal Connector Framework baseline.
- Recommended post-merge release tag: `v1.1.0-universal-connectors`.

## v1.0.0-enterprise-foundation - 2026-07-05

### Added
- Enterprise Business Architecture pages for business units, capabilities, services, processes, and enterprise capability mapping.
- Shared Platform Framework for executive summaries, reconciliation, business context, AI narratives, evidence panels, certification banners, and portfolio summaries.
- Enterprise Financial Model for canonical allocation, reconciliation, variance, and business-to-technology financial lineage.
- Certification services for Executive and CIO workspaces.
- Technology Digital Twin and Knowledge Graph standardization for CIO intelligence workflows.
- Streamlit compatibility helpers for modern table and chart rendering.
- Platform service layer for formatting, reconciliation, evidence, certification, and narrative composition.

### Changed
- Standardized Executive, CIO, and Business Architecture workspaces around certification-grade evidence, reconciliation, and business context.
- Modernized CIO workspace table and chart rendering through compatibility wrappers.
- Improved sidebar navigation and business architecture entry points.
- Introduced service payload caching for analytical dashboards and canonical platform rollups.

### Performance
- Repository reads use Streamlit cache data patterns where available.
- Enterprise Financial Model cached at 300 seconds.
- Business Context base payload cached at 600 seconds.
- Analytical certification dashboards cached at 300 seconds.
- Risk & Governance analytical payload cached at 120 seconds with live approval queue detail.

### Validation
- Certified Executive, CIO, and Business Architecture pages compile successfully.
- 18 key Streamlit routes return 200 OK in local release validation.
- Approval actions and mutation paths remain uncached.

### Notes
- Local screenshot and generated twin JSON artifacts are excluded from release commits.
- CIO workspace remains provisionally certified pending future dashboard-level performance evidence.

