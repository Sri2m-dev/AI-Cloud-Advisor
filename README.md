# AI-Cloud-Advisor

AI Cloud Advisory Platform built with Streamlit.

## Entry Point

- [app.py](c:\Users\SrikanthMudaliar\AI-Cloud-Advisor\app.py): active Streamlit entrypoint and main routing shell.

## Python Version

This project targets Python 3.11.

## Local Setup

1. Install dependencies.

```bash
pip install -r requirements.txt
```

2. Copy the environment template.

```bash
copy .env.example .env
```

3. Start the app locally.

```bash
streamlit run app.py
```

4. Open the local URL shown by Streamlit, typically `http://localhost:8501`.

## Streamlit Cloud Deployment

1. Deploy [app.py](c:\Users\SrikanthMudaliar\AI-Cloud-Advisor\app.py) as the app entrypoint.
2. Add the required secrets from [.streamlit/secrets.toml.example](c:\Users\SrikanthMudaliar\AI-Cloud-Advisor\.streamlit\secrets.toml.example) into the Streamlit Cloud secrets manager.
3. Make sure the deployed database contains the client users you intend to share access with.
4. Confirm the deployed app opens your branded login page directly rather than a Streamlit platform access gate.
5. Log in with a non-admin client account and verify the selected plan hides unavailable pages.

For a detailed checklist, see [DEPLOYMENT.md](c:\Users\SrikanthMudaliar\AI-Cloud-Advisor\DEPLOYMENT.md).

## Testing And Quality

Run unit tests:

```bash
pytest -q
```

Run linting:

```bash
ruff check .
```

Run type checks:

```bash
mypy
```

## CI

GitHub Actions workflow is defined in `.github/workflows/ci.yml` and runs on push and pull request with Python 3.11 plus linting, typing, and tests.
