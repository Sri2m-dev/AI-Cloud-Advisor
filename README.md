# AI-Cloud-Advisor

AI Cloud Advisory Platform built with Streamlit.

## Project Structure

- `app.py`: main Streamlit entrypoint and login shell.
- `1_Dashboard.py`: dashboard KPIs and chart.
- `2_Cost_Explorer.py`: CUR upload and spend exploration.
- `3_Optimization.py`: optimization recommendation view.
- `4_Reports.py`: reports placeholder page.
- `cost_loader.py`: cost CSV loading helpers.
- `finops_metrics.py`: FinOps calculations.
- `ai_recommender.py`: recommendation generation logic.
- `config.py`: centralized runtime configuration from environment variables.

## Python Version

This project targets Python 3.11.

## Local Setup

1. Install dependencies:

	 ```bash
	 pip install -r requirements.txt
	 ```

2. (Optional) Configure environment variables:

	 ```bash
	 cp .env.example .env
	 ```

3. Start the app:

	 ```bash
	 streamlit run app.py
	 ```

## Testing And Quality

- Run unit tests:

	```bash
	pytest -q
	```

- Run linting:

	```bash
	ruff check .
	```

- Run type checks:

	```bash
	mypy
	```

## CI

GitHub Actions workflow is defined in `.github/workflows/ci.yml` and runs on push/PR with:

- Python 3.11
- `ruff check .`
- `mypy`
- `pytest -q`
