# Nexora Deployment Guide

Status: v1.0.0 foundation baseline
Scope: Streamlit application deployment, environment configuration, validation, and rollback guidance.

## Runtime Overview

Nexora runs as a Streamlit application backed by Supabase and optional AI/provider integrations.

Primary entry point:

```powershell
python -m streamlit run app_main.py
```

Recommended local validation port:

```powershell
python -m streamlit run app_main.py --server.port 8513
```

## Required Environment Variables

See `NEXORA_ENVIRONMENT_CONFIGURATION.md` for the authoritative variable list.

Minimum production baseline:

```env
SUPABASE_URL=...
SUPABASE_KEY=...
DEFAULT_ORG_ID=...
ENVIRONMENT=production
OPENAI_API_KEY=...
```

## Deployment Steps

1. Pull the approved release branch or tag.
2. Install dependencies from the project requirements.
3. Configure environment variables in the deployment platform.
4. Start Streamlit with `app_main.py`.
5. Validate login and role-based landing pages.
6. Run route smoke checks for the release route set.
7. Confirm logs show no import errors or missing environment variables.

## Post-Deployment Smoke Routes

Validate these routes after deployment:

- `/executive_dashboard`
- `/enterprise_spend`
- `/approval_center`
- `/reports`
- `/cio_dashboard`
- `/technology_health`
- `/technology_inventory`
- `/technology_knowledge_graph`
- `/technology_digital_twin`
- `/application_inventory`
- `/saas_intelligence`
- `/risk_governance`
- `/business_architecture`
- `/business_units`
- `/business_capabilities`
- `/business_services`
- `/business_processes`
- `/enterprise_capability_map`

## Rollback

Rollback should use a previously validated tag or release branch.

Recommended rollback flow:

1. Identify last stable release tag.
2. Redeploy from that tag.
3. Confirm environment variables are unchanged.
4. Run the same smoke route set.
5. Record rollback cause in release notes or incident log.

## Deployment Notes

- Do not deploy local generated JSON artifacts.
- Do not commit screenshots or Streamlit runtime cache.
- Keep approval actions uncached.
- Verify Supabase values match the intended environment before production validation.
