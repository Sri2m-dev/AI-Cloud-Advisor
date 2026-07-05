# Nexora Operations Runbook

Status: v1.0.0 foundation baseline
Scope: Operational checks, incident triage, cache behavior, and support procedures.

## Daily Health Checks

1. Confirm application is reachable.
2. Confirm login works for expected roles.
3. Confirm Executive and CIO landing pages load.
4. Confirm no Streamlit tracebacks appear in logs.
5. Confirm Supabase-backed metrics are populated.
6. Confirm approval queues are live where applicable.

## Standard Smoke Test

Use the 18-route release validation set documented in `NEXORA_DEPLOYMENT_GUIDE.md`.

Expected result:

```text
18/18 routes return HTTP 200
No Streamlit traceback
No missing environment variable error
```

## Common Issues

### Supabase data shows zero or missing values

Check:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `DEFAULT_ORG_ID`
- Environment-specific table availability
- Supabase permissions and row-level security

### Login fails locally

Check:

- Auth source used by current branch
- Environment variables
- Local demo fallback behavior if enabled for development

### Reports page loads but schedule/PDF actions disabled

This may be expected if backend report dependencies or environment variables are unavailable. The page should still render.

### Approval queue appears stale

The approval queue detail is intentionally live and uncached. Check service connectivity and approval service logs before clearing application cache.

## Cache Operations

Caching is conservative and service-level.

If stale analytical data is suspected:

1. Wait for TTL expiration.
2. Restart Streamlit if immediate reset is required.
3. Do not alter mutation/action caching rules.

## Incident Triage

Capture:

- User role
- Route
- Timestamp
- Environment
- Screenshot if UI-specific
- Terminal or platform logs
- Recent release or configuration changes

Classify:

| Severity | Description |
| --- | --- |
| Sev 1 | Application unavailable or auth broken for all users |
| Sev 2 | Certified workspace unavailable |
| Sev 3 | Single page/data panel degraded |
| Sev 4 | Cosmetic or documentation issue |

## Escalation

Escalate Sev 1 and Sev 2 issues immediately to the release owner. Sev 3 issues should be assigned to the owning domain service. Sev 4 issues can be handled in the next maintenance cycle.
