# Nexora Enterprise Intelligence Platform

Nexora is an Enterprise Intelligence and Decision Platform for executive, CIO, business architecture, cloud, SaaS, governance, connector, and AI-driven operational intelligence.

This repository is the proposed canonical codebase for the v1.1.0 Universal Connector Framework release baseline.

## Current Release Baseline

```text
Current program:
P2 - Universal Connector Framework

Current release candidate:
v1.1.0-universal-connectors

Canonical application entrypoint:
app_main.py
```

The release tag must be created only after repository cutover and E8.1.17 post-merge validation pass.

## Architecture Summary

Nexora is organized as a layered enterprise platform:

```text
Streamlit Pages
    -> Shared Platform Framework
    -> Certification Services
    -> Business Services
    -> Repositories
    -> Supabase / External Data Sources

Universal Connector Framework
    -> Connector SDK
    -> Registry
    -> Runtime
    -> Authentication and Secrets
    -> Normalization
    -> Persistence
    -> Orchestration
    -> Observability
    -> Provider Adapters
```

Key platform capabilities include:

- Executive Workspace
- CIO Workspace
- Business Architecture
- Enterprise Financial Model
- Knowledge Graph
- Technology Digital Twin
- Shared Platform Framework
- Universal Connector Framework
- AWS, Azure, and GCP runtime adapter foundations

## How to Run Locally

Create a local environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional development dependencies:

```powershell
pip install -r requirements-dev.txt
```

Start the Streamlit app:

```powershell
python -m streamlit run app_main.py --server.port 8513
```

## Required Environment Variables

Use `.env.example` or `.streamlit/secrets.toml.example` as templates. Do not commit real secrets.

Minimum local baseline:

```text
SUPABASE_URL
SUPABASE_KEY
DEFAULT_ORG_ID
ENVIRONMENT
```

Conditional variables:

```text
OPENAI_API_KEY
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_DEFAULT_REGION
AZURE_TENANT_ID
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
AZURE_SUBSCRIPTION_ID
GCP_PROJECT_ID
GCP_SERVICE_ACCOUNT_SECRET_REF
```

For full details, see `docs/NEXORA_ENVIRONMENT_CONFIGURATION.md`.

## Key Routes

Executive workspace:

- `/executive_dashboard`
- `/enterprise_spend`
- `/approval_center`
- `/reports`

CIO workspace:

- `/cio_dashboard`
- `/technology_health`
- `/technology_inventory`
- `/technology_knowledge_graph`
- `/technology_digital_twin`
- `/application_inventory`
- `/saas_intelligence`
- `/risk_governance`

Business Architecture:

- `/business_architecture`
- `/business_units`
- `/business_capabilities`
- `/business_services`
- `/business_processes`
- `/enterprise_capability_map`

Connector operations:

- `/connector_operations`
- `/connector_studio`
- `/cloud_connections`
- `/aws_connector_setup`
- `/azure_connector_setup`

## Release Process

The v1.1.0 release should follow this sequence:

```text
1. Complete repository source-of-truth cutover.
2. Merge the canonical recovery baseline into official main.
3. Run E8.1.17 Post-Merge Release Gate.
4. Review docs/E8_1_17_RELEASE_VALIDATION.md.
5. Tag v1.1.0-universal-connectors only if validation is GO.
6. Push the tag.
7. Close Program P2.
```

Do not start Program P3 / Enterprise Data Fabric until the v1.1.0 tag is complete.

## Documentation Index

Repository governance:

- `docs/REPOSITORY_CONSOLIDATION_ASSESSMENT.md`
- `docs/SOURCE_OF_TRUTH_CUTOVER_PLAN.md`
- `docs/GITHUB_CUTOVER_RUNBOOK.md`
- `docs/REPOSITORY_SELF_CONTAINMENT_AUDIT.md`

Release documentation:

- `docs/NEXORA_RELEASE_NOTES_v1.1.0.md`
- `docs/NEXORA_RELEASE_CHECKLIST_v1.1.0.md`
- `docs/NEXORA_v1.1.0_FEATURE_MATRIX.md`
- `docs/E8_1_RELEASE_REVIEW.md`

Architecture:

- `docs/NEXORA_PLATFORM_ARCHITECTURE.md`
- `docs/ARCHITECTURE_DECISION_INDEX.md`
- `docs/architecture/ADR-001-Shared-Platform-Framework.md`
- `docs/architecture/ADR-002-Enterprise-Financial-Model.md`
- `docs/architecture/ADR-003-Knowledge-Graph.md`
- `docs/architecture/ADR-004-Digital-Twin.md`
- `docs/architecture/ADR-005-Certification-Framework.md`
- `docs/architecture/ADR-006-Caching-Strategy.md`
- `docs/architecture/ADR-007-Universal-Connector-Framework.md`

Operations:

- `docs/NEXORA_DEPLOYMENT_GUIDE.md`
- `docs/NEXORA_ENVIRONMENT_CONFIGURATION.md`
- `docs/NEXORA_OPERATIONS_RUNBOOK.md`
- `docs/NEXORA_BACKUP_RECOVERY_GUIDE.md`
- `docs/NEXORA_CACHING_STRATEGY.md`
