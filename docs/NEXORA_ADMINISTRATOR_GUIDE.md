# Nexora Administrator Guide

Status: v1.0.0 foundation baseline
Scope: Administrative responsibilities, roles, environment setup, and operational governance.

## Administrator Responsibilities

Administrators are responsible for:

- Environment variable configuration
- Supabase access and data source health
- Role and organization alignment
- Deployment validation
- Release coordination
- Backup and rollback readiness
- Incident triage and operational communication

## Roles

Nexora supports role-based navigation and landing experiences for:

- Executive
- CIO
- Finance
- Super Admin
- Technical

Role behavior is implemented through the application navigation and session model. Administrators should validate role access after major releases.

## Environment Management

Each environment should define:

- Supabase project URL and key
- Default organization identifier
- Runtime environment name
- AI provider keys where enabled
- Any backend/reporting service variables required by deployment

Do not share production secrets through source control, screenshots, or documentation examples.

## Data Source Management

Key data domains include:

- Business Architecture
- Application Portfolio
- Technology Inventory
- SaaS Intelligence
- Enterprise Spend
- Approval Requests
- Recommendations
- Knowledge Graph relationships
- Technology Digital Twins

Administrators should monitor whether expected data sources are live or derived from fallback logic.

## Release Administration

Before approving a release:

1. Confirm validation report is complete.
2. Confirm documentation freeze is complete.
3. Confirm `.gitignore` excludes local artifacts.
4. Confirm release notes and changelog are updated.
5. Confirm route smoke checks pass.
6. Confirm rollback tag or branch is available.

## Security Notes

- Keep service keys out of source control.
- Use least privilege where deployment platform supports it.
- Review Supabase row-level security before production use.
- Treat approval actions and financial data as sensitive workflows.

## Support Checklist

When users report issues, collect:

- Role
- Route
- Browser
- Environment
- Time observed
- Expected behavior
- Actual behavior
- Screenshot or traceback
