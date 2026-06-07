# AI Cloud Advisor - TEST Environment

This folder creates a **separate TEST environment** for controlled integration.

## Purpose
- **Demo (`demo_ceo/`)**: client-facing and stable
- **Dev (`Dev/`)**: build and experiment
- **Test (`test_env/`)**: validate service-layer integration safely

## Chosen approach
**Option A: Mock API + partial backend**

Flow:
```text
UI (same dashboards) -> Service Layer -> Mock API -> later real AWS/API
```

## What is different here
- `test_env/app.py` is a dedicated Streamlit entrypoint for TEST mode.
- `test_env/data_loader.py` replaces direct JSON access with `fetch_cost_data_from_service()`.
- `test_env/test_support/cost_service.py` provides:
  - service-layer fetching
  - logging and error handling
  - safe action persistence
  - gradual hooks into `services/finops_engine.py` and `services/aws_connector.py`
- `test_env/data/test_cost_data.json` is isolated test data, so Demo/Dev are not mixed.

## Run locally
```powershell
streamlit run test_env/app.py
```

## Validation checklist
- Data loads from the service layer
- Dashboards still render
- Drill-down navigation still works
- Action updates persist in the test payload
- Missing fields fail safely
- API/service failures show a user-friendly error path

## Next integration steps
1. Replace the mock payload in `fetch_cost_data_from_service()` with a real internal API.
2. Connect `aws_connector.py` for controlled live reads.
3. Expand `finops_engine.py` outputs into recommendations and anomaly signals.
