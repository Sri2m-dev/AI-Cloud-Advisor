# Nexora Environment Configuration

Status: v1.0.0 foundation baseline
Scope: Runtime variables and configuration expectations.

## Required Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | Yes | Supabase project endpoint |
| `SUPABASE_KEY` | Yes | Supabase API key used by backend services |
| `DEFAULT_ORG_ID` | Yes | Default organization context for dashboard queries |
| `ENVIRONMENT` | Yes | Runtime environment, for example `production` or `development` |
| `OPENAI_API_KEY` | Conditional | Required when AI features call OpenAI-backed services |

## Optional Variables

Optional variables may be required by specific integrations, report generation, connector operations, or future Data Fabric services.

Administrators should document environment-specific additions in deployment notes.

## Local Development Example

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
DEFAULT_ORG_ID=your_default_org_id
ENVIRONMENT=production
OPENAI_API_KEY=your_openai_key
```

Do not commit `.env` files.

## Validation

After changing environment variables:

1. Restart Streamlit.
2. Confirm login works.
3. Confirm Executive Dashboard has populated data.
4. Confirm CIO Dashboard has populated data.
5. Confirm Business Architecture pages render.
6. Confirm Reports page loads even if optional report backend actions are unavailable.

## Common Misconfiguration Symptoms

| Symptom | Likely Cause |
| --- | --- |
| `$0` spend values | Missing or wrong Supabase/organization configuration |
| Login failure | Auth source mismatch or missing environment values |
| Supabase URL required error | Missing `SUPABASE_URL` |
| Empty tables | Wrong organization ID, missing data, or table permissions |
| AI panels unavailable | Missing AI provider key or disabled integration |

## Secret Handling

- Store secrets only in deployment environment settings or local `.env` files.
- Never commit secrets.
- Rotate exposed keys immediately.
- Avoid screenshots that reveal environment values.
