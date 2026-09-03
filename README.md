# Nexora

**Enterprise Decision Intelligence Platform**

Nexora connects executive and CIO workspaces, business architecture, financial
intelligence, governance, Universal Connectors, and a canonical Enterprise Data Fabric into
an evidence-backed environment for enterprise technology decisions.

## Current release candidate

```text
Release: Nexora 2.0.0
Authoritative version: nexora_release.py
Certified through: ACT-013 / ACT-C13
Application entry point: app_main.py
Python: 3.11
```

Release-facing guidance is consolidated in
`docs/release/REL_001_RELEASE_CANDIDATE.md`. ACT/PUE documents remain engineering history.

## Architecture

```text
Workspaces and Reports
    -> Business and Certification Services
    -> Knowledge Graph / Digital Twin / Intelligence
    -> Enterprise Data Fabric
    -> Universal Connectors
    -> Supabase and External Systems
```

The Data Fabric provides canonical entities and relationships, identity resolution, semantic ontology, versioning, lineage, provenance, data quality, tenant isolation, idempotency, and secured atomic write RPCs. It is not yet wired as a replacement for every legacy runtime read path.

See `docs/NEXORA_ENTERPRISE_ARCHITECTURE.md`, `docs/NEXORA_DATA_FABRIC.md`, `docs/ARCHITECTURE_DECISION_INDEX.md`, and `docs/P3_DATA_FABRIC_RELEASE_GATE.md`.

## Local setup

Use Python 3.11 and `.env.example` as the configuration template. Never commit secrets.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt `
  -r requirements-prod.txt -r requirements.frontend.txt `
  -r backend\requirements.txt
python -m pip check
```

Start the application:

```powershell
python -m streamlit run app_main.py --server.port 8513
```

Environment guidance is in `docs/NEXORA_ENVIRONMENT_CONFIGURATION.md`. P3 live validation uses separate `P3_SUPABASE_*` variables and is opt-in only; ordinary local and CI commands do not use live credentials.

## Certified validation

```powershell
python -m pytest --collect-only -q
python -m pytest -q
```

ACT-013 frozen certification:

- Full suite: 1,696 passed, 2 expected opt-in skips, 0 failed.
- ACT-C13: Integrated Production Journey Certified.

Exact commands and scope are recorded in `docs/RELEASE_REPRODUCTION.md`, `docs/REPOSITORY_HEALTH_PHASE1.md`, `docs/CI_CERTIFICATION.md`, and `docs/P3_SUPABASE_LIVE_VALIDATION_CHECKPOINT.md`.

## Release boundary

REL-001 supersedes the historical paragraph below for this candidate: release `2.0.0` must
complete REL-002 fresh-clone/deployment certification before any merge or tag decision.

The release candidate must pass documentation review and subsequent merge preparation before governance can authorize merge. If approved, merge the feature branch into `main`, verify the reviewed merge commit, and tag that merge commit—not a feature-branch commit—as `v1.2.0-data-fabric`.

Do not merge, tag, or begin new architecture or feature implementation solely from this README.
