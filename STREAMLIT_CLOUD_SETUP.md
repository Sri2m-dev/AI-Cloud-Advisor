# Streamlit Cloud Deployment Setup

## Recommended app target
- **Main file path:** `Dev/app.py`
- **Python version:** `3.11.9` (from `runtime.txt`)
- **Dependencies file:** `requirements.txt`

## Why this is ready
- `Dev/app.py` is the active Streamlit entrypoint.
- It already adds the repo root to `sys.path`, so imports from `shared/`, `services/`, and `database/` work on Streamlit Cloud.
- `requirements.txt` includes the core app libraries, including `streamlit`, `pandas`, `plotly`, `supabase`, and `fpdf2`.

## Secrets to add in Streamlit Cloud
Copy the values from `.streamlit/secrets.toml.example` into the Streamlit Cloud **Secrets** panel.

Minimum recommended keys:
```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-supabase-key"
PGDATABASE = "cloud_advisor"
PGUSER = "your_postgres_user"
PGPASSWORD = "your_postgres_password"
PGHOST = "your_postgres_host"
PGPORT = "5432"
CLOUD_ADVISOR_CREDENTIAL_KEY = "replace-with-a-long-random-secret"
CLOUD_ADVISOR_APP_URL = "https://your-app.streamlit.app"
JWT_SECRET = "replace-with-a-long-random-secret"
```

Optional keys for extended features:
```toml
STRIPE_SECRET_KEY = "sk_live_or_test_key"
OPENAI_API_KEY = "your-openai-key"
AWS_ACCESS_KEY_ID = "your-aws-access-key"
AWS_SECRET_ACCESS_KEY = "your-aws-secret-key"
AWS_DEFAULT_REGION = "us-east-1"
YAGMAIL_USER = "reports@yourcompany.com"
YAGMAIL_PASSWORD = "app-password"
FEEDBACK_REPORT_EMAIL_TO = "ops@yourcompany.com"
```

## Streamlit Cloud steps
1. Push the repository to GitHub.
2. In Streamlit Cloud, click **New app**.
3. Select the repo and branch.
4. Set **Main file path** to `Dev/app.py`.
5. Add the secrets above in the **Secrets** section.
6. Deploy.

## Notes
- The app currently supports the live demo flow and mock-data fallback.
- `shared/db.py` now reads `SUPABASE_URL` and `SUPABASE_KEY` from environment variables or Streamlit secrets first, which makes cloud deployment cleaner.
- Keep `.streamlit/secrets.toml` out of git; the repo already ignores it.
