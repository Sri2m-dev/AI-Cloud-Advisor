# Nexora Backup and Recovery Guide

Status: v1.0.0 foundation baseline
Scope: Source recovery, release tags, environment recovery, and data backup responsibilities.

## Source Recovery

Nexora releases should be recoverable through Git tags and release branches.

Recommended baseline tag:

```text
v1.0.0-enterprise-foundation
```

Recovery steps:

1. Checkout the last known good tag or release branch.
2. Restore environment variables for the target environment.
3. Start Streamlit.
4. Run the 18-route smoke validation set.
5. Confirm role-based login and critical workspace access.

## Local Artifact Exclusions

The following should not be part of source recovery:

- Local screenshots
- Generated digital twin JSON files
- Streamlit runtime cache
- Python cache artifacts
- Local `.env` files

## Data Backup

Supabase data backup is owned by the Supabase/project administration process.

Recommended backup coverage:

- Business Architecture tables
- Application registry
- Technology inventory
- Spend marts
- Approval requests
- Recommendations
- Knowledge Graph relationships
- Digital Twin data
- Audit or governance evidence where available

## Environment Recovery

Maintain a secure record of required deployment variables:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `DEFAULT_ORG_ID`
- `ENVIRONMENT`
- AI provider keys where enabled

Do not store plaintext production secrets in the repository.

## Rollback Criteria

Rollback may be required when:

- Authentication is unavailable.
- Certified Executive or CIO workspace routes fail.
- Supabase configuration prevents data access across multiple domains.
- Approval actions fail after deployment.
- A release introduces broad UI regression.

## Recovery Validation

A successful recovery requires:

```text
Compile: PASS
Routes: PASS
Login: PASS
Executive Workspace: PASS
CIO Workspace: PASS
Business Architecture: PASS
No critical traceback: PASS
```

## Future Enhancements

- Automated database backup verification.
- Scheduled export of release validation reports.
- Disaster recovery runbooks for each deployment environment.
- Restore drills before major enterprise releases.
