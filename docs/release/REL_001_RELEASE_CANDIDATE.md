# Nexora 2.0.0 Release Candidate

## Baseline

- Product version: `2.0.0` from `nexora_release.py`.
- Certified baseline: `d68d6450fa23c5c3a44efc0371a290627c9b29e6`.
- Entry point: `python -m streamlit run app_main.py`.
- Runtime: CPython 3.11 (`runtime.txt` pins 3.11.9).
- Certification: ACT-013 PASS; ACT-C13 PASS.

## Architecture and contexts

The entry point runs the replay-safe Universal Evidence migration and constructs the
durable runtime before authenticated routing. Pages consume the shared
`active_workspace_context` authority.

- **DEMO:** opt-in immutable `SYNTHETIC_DEMONSTRATION_DATA`, Demo tenant only.
- **PROSPECT:** encrypted evidence bound to organization, tenant, prospect, and analysis;
  unsupported conclusions remain UNKNOWN or BLOCKED.
- **TENANT:** authenticated governed tenant sources only, with no Demo/prospect fallback.

## Install and start

```powershell
python -m pip install -r requirements.txt -r requirements-prod.txt `
  -r requirements.frontend.txt -r backend\requirements.txt
python -m streamlit run app_main.py
```

Install `requirements-dev.txt` only for development/testing. Ports 8513 and 8522 are local
examples, not production requirements.

## Migrations and operations

Universal Evidence migration `0001` runs transactionally before durable composition and is
replay-safe and fail-closed. Data Fabric migrations `0001`-`0020` and dated Supabase
migrations remain approved deployment artifacts applied in order by an authorized process.
Back up authoritative data and verify restore before upgrade. Streamlit `_stcore/health` is
liveness; readiness additionally requires configuration, migrations, persistence, auth, and
dependency checks.

## Release documentation map

- Architecture: `docs/NEXORA_ENTERPRISE_ARCHITECTURE.md`
- Configuration/security: `docs/release/PRODUCTION_CONFIGURATION.md`
- Deployment: `docs/NEXORA_DEPLOYMENT_GUIDE.md`
- Universal Evidence: `docs/NEXORA_DATA_FABRIC.md` and `docs/pue/`
- Operations/recovery: `docs/NEXORA_OPERATIONS_RUNBOOK.md` and
  `docs/NEXORA_BACKUP_RECOVERY_GUIDE.md`
- Certification: `docs/acceptance/ACT_013_PRODUCTION_ACCEPTANCE.md`
- Limitations/debt: `docs/release/KNOWN_LIMITATIONS.md`
- History: `CHANGELOG.md`

REL-002, not this bounded pre-check, is the authoritative fresh-clone/deployment
certification.
