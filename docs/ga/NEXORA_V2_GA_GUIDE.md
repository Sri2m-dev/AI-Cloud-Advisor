# Nexora v2.0 GA Guide

## Product purpose

Nexora is an evidence-backed technology decision control plane. It composes existing
financial, architecture, operations, risk, governance, and intelligence services without
replacing their systems of record.

Nexora v2.0 supports three executive decisions:

1. Approve, defer, resize, or reject a technology investment.
2. Retain, consolidate, modernize, renegotiate, or retire portfolio assets.
3. Understand and mitigate material business-service technology risk.

## Five-minute executive test

For every major workspace, a first-time executive must be able to identify what to do, why
now, what happens without action, the affected outcomes, the evidence, uncertainty, owner,
and decision authority. The story is ordered as yesterday, today, risk, recommendation,
business outcome, and action. Narratives do not grant decision or execution authority.

## Data truthfulness

- Zero is displayed only when an available certified source reports zero.
- An absent source is `UNKNOWN`; partial and conflicted evidence remains visible.
- Potential, approved, executed, and verified realized value remain distinct.
- UI and exports do not invent business calculations.
- Certified metrics retain tenant, source, freshness, and availability context.

## Synthetic demonstration tenant

The bundled dataset is disabled by default. Enable it only in a demonstration environment:

```env
NEXORA_DEMO_MODE=true
```

The authenticated organization ID must begin with `demo-`; the bundled tenant is
`demo-nexora-global-retail`. The application rejects synthetic data for any other tenant.
The dataset is immutable JSON, is never written to production repositories or marts, and is
labeled throughout the Executive Experience. Never enable demo mode in customer production.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt `
  -r requirements-prod.txt -r requirements.frontend.txt `
  -r backend\requirements.txt
python -m streamlit run app_main.py --server.port 8513
```

Container reference deployment:

```powershell
docker compose -f docker-compose.deploy.yml build
docker compose -f docker-compose.deploy.yml up -d
```

The frontend starts `app_main.py`. The build context excludes secrets, local databases,
logs, caches, exports, and development artifacts.

## Production configuration and validation

Start from `.env.example`, keep real secrets in the deployment secret manager, and review
`docs/NEXORA_ENVIRONMENT_CONFIGURATION.md`. Validate authentication, RLS, tenant identity,
encryption, provider integrations, persona routes, the three decisions, report reconciliation,
logs, monitoring, backup, restore, and rollback ownership.

## Upgrade and rollback

Record the current artifact digest, back up authoritative data, and verify restoration before
upgrade. Deploy immutable artifacts. If a gate fails, stop rollout, preserve audit evidence,
restore the previous artifact, execute the approved data recovery procedure where required,
and rerun authentication, tenancy, financial-integrity, and audit checks.

## Known limitations

- Certified output depends on customer source availability and quality.
- Missing customer marts intentionally produce `UNKNOWN`.
- Browser automation may require documented manual evidence when unavailable.
- Commercial ROI remains subject to customer validation.
- v2.0 does not claim autonomous executive decisions or production remediation.
