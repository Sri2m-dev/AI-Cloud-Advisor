# Deployment Checklist

## Goal

Use this checklist before sharing the public app URL with a client.

## Streamlit Cloud Setup

1. Deploy [app.py](c:\Users\SrikanthMudaliar\AI-Cloud-Advisor\app.py) as the main file.
2. Confirm all Python dependencies from [requirements.txt](c:\Users\SrikanthMudaliar\AI-Cloud-Advisor\requirements.txt) install successfully in Streamlit Cloud.
3. Add secrets from [.streamlit/secrets.toml.example](c:\Users\SrikanthMudaliar\AI-Cloud-Advisor\.streamlit\secrets.toml.example).
4. If the app is public-facing, confirm viewers land on the app login page rather than a Streamlit platform auth gate.

## Required Runtime Configuration

The app currently relies on these values for production:

- Database: `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`
- Encryption: `CLOUD_ADVISOR_CREDENTIAL_KEY`
- Billing checkout: `CLOUD_ADVISOR_APP_URL`, `STRIPE_SECRET_KEY`
- Optional email reports: `YAGMAIL_USER`, `YAGMAIL_PASSWORD`, `FEEDBACK_REPORT_EMAIL_TO`
- Optional signup: `SUPABASE_URL`, `SUPABASE_KEY`
- Optional AI features: `OPENAI_API_KEY`
- Optional cloud integrations: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`

## Pre-Share Validation

1. Open the deployed URL in an incognito browser window.
2. Confirm the app loads without a `500` error.
3. Confirm login works with a non-admin client account.
4. Confirm the client account has the correct plan selected in Plans & Billing.
5. Confirm restricted pages are hidden based on pack.
6. Confirm reports generate in the deployed environment.
7. Confirm billing checkout opens Stripe, returns to Plans & Billing, and activates the selected trial plan.
8. Confirm billing and recommendation data come from the correct deployed database.

## Commercial Pack Validation

Current plan behavior in code:

1. `Starter`: $150/month or $1440/year, 7-day trial, 2 user licenses, 1 cloud account, 30-day billing history.
2. `Growth`: $250/month or $2400/year, 7-day trial, 5 user licenses, 5 cloud accounts, 180-day billing history.
3. `Enterprise`: $500/month or $4800/year, 7-day trial, unlimited users, unlimited cloud accounts, unlimited billing history.

## Sharing With Clients

When the deployment is verified, share:

1. The public URL.
2. The client username and password.
3. Their selected pack.
4. A short summary of included seats, cloud-account limits, and enabled modules.

## Known Production Gaps

The current app still uses a simple username and password lookup in the local application database. For stronger production security and tenant isolation, move authentication and subscription ownership to a managed identity provider or tenant-aware backend.