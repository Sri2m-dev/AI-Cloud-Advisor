def detect_format(df):
    cols = [c.lower() for c in df.columns]
    if "line_item_product_code" in cols:
        return "cur"
    if "service" in cols and "cost" in cols:
        return "simple"
    if "linked account name" in str(df.iloc[0].values).lower():
        return "finance"
    return "unknown"
def transform_finance_excel(df):
    """
    Transforms a finance-style Excel DataFrame into the service model.
    """
    df.columns = ["account"] + [f"month_{i}" for i in range(len(df.columns)-1)]
    df["total_cost"] = df.iloc[:, 1:].sum(axis=1)
    services = [
        {
            "name": row["account"],
            "cost": row["total_cost"],
            "savings": round(row["total_cost"] * 0.12, 2),
            "cloud": "FinanceExcel",
        }
        for _, row in df.iterrows()
    ]
    total_spend = sum(row["total_cost"] for _, row in df.iterrows())
    return {
        "total_spend": total_spend,
        "services": services,
    }

def empty_safe_response():
    return {"total_spend": 0.0, "services": []}
def load_finance_excel(file_path):
    """
    Loads a finance-style Excel file and maps accounts to services with monthly totals as spend.
    Steps:
    1. Clean header (skip first 2 rows)
    2. Rename columns: ["account", "month_0", ...]
    3. Compute total_cost per account
    4. Map to service model
    """
    df = pd.read_excel(file_path, skiprows=2)
    df.columns = ["account"] + [f"month_{i}" for i in range(len(df.columns)-1)]
    df["total_cost"] = df.iloc[:, 1:].sum(axis=1)
    services = [
        {
            "name": row["account"],
            "cost": row["total_cost"],
            "savings": round(row["total_cost"] * 0.12, 2),
            "cloud": "FinanceExcel",
        }
        for _, row in df.iterrows()
    ]
    total_spend = sum(row["total_cost"] for _, row in df.iterrows())
    return {
        "total_spend": total_spend,
        "services": services,
    }
import logging
from pathlib import Path

import pandas as pd

## Legacy cost_service import removed. Use services.cost_service instead.

logger = logging.getLogger(__name__)
TEST_DATA_PATH = Path(__file__).resolve().parent / "data" / "test_cost_data.json"
ROOT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CUR_EXCEL_PATH = ROOT_DATA_DIR / "CUR Jan 2026.xlsx"


def _finalize_cost_frame(df):
    if df.empty:
        return df

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


def _default_payload():
    return {
        "last_updated": None,
        "total_spend": 0,
        "previous_spend": 0,
        "services": [],
        "actions": [],
        "source": "Test Service Fallback",
        "service_mode": "engine",
        "cost_engine_status": "Error",
        "aws_connector_mode": "Unavailable",
        "error_message": "Test data loader fallback in use",
    }


def _payload_to_cost_frame(payload, client_id=None):
    services = payload.get("services", []) or []
    if not services:
        return pd.DataFrame()

    default_date = payload.get("last_updated")
    records = []
    for service in services:
        records.append(
            {
                "client_id": client_id,
                "service_name": service.get("service_name") or service.get("name", "Other"),
                "cost": service.get("cost", 0),
                "potential_savings": service.get(
                    "potential_savings",
                    service.get("savings", 0),
                ),
                "cloud": service.get("cloud", "AWS"),
                "date": service.get("date", default_date),
            }
        )

    return _finalize_cost_frame(pd.DataFrame(records))



def load_cur_excel_clean(file_path):
    df = pd.read_excel(file_path, skiprows=3)
    df.columns = df.columns.map(lambda value: str(value).strip())
    # Support both CUR and Finance Excel formats
    if "line_item_product_code" in df.columns:
        return transform_cur_data(df)
    elif "Linked account name" in df.iloc[0].values:
        return transform_finance_excel(df)
    else:
        return empty_safe_response()



def transform_cur_data(df):

    # Step 1: Debug print columns and sample rows
    print("DEBUG → Columns:", df.columns.tolist())
    print("DEBUG → Sample rows:", df.head(3))

    # Step 2: Robust dynamic mapping
    df.columns = [c.strip().lower() for c in df.columns]

    # Auto-detect columns
    service_col = None
    cost_col = None

    for col in df.columns:
        if "service" in col or "product" in col:
            service_col = col
        if "cost" in col:
            cost_col = col

    if not service_col or not cost_col:
        return {"total_spend": 0.0, "services": []}

    grouped = df.groupby(service_col)[cost_col].sum().reset_index()

    services = []
    total = grouped[cost_col].sum()

    for _, row in grouped.iterrows():
        services.append({
            "name": row[service_col],
            "cost": float(row[cost_col]),
            "savings": 0
        })

    return {
        "total_spend": float(total),
        "services": services
    }

    service_key = normalized["service"].str.lower()
    excluded_patterns = (
        r"^(total|grand total|subtotal|account number|supporting document attached|generated on)$"
    )
    normalized = normalized[
        (normalized["service"] != "")
        & (~service_key.str.match(excluded_patterns, na=False))
    ]

    grouped = (
        normalized.groupby("service", as_index=False)["cost"]
        .sum()
        .sort_values("cost", ascending=False)
    )
    grouped = grouped[grouped["cost"] > 0]
    if grouped.empty:
        return {"total_spend": 0.0, "services": []}

    services = []
    total_spend = 0.0
    for _, row in grouped.iterrows():
        cost_value = float(row["cost"])
        services.append(
            {
                "service": str(row["service"]),
                "cost": cost_value,
                "savings": round(cost_value * 0.2, 2),
                "resources": []
            }
        )
        total_spend += cost_value

    return {
        "total_spend": float(total_spend),
        "services": services,
        "actions": [],
        "cost_engine_status": "Healthy",
        "service_mode": "CUR File",
        "aws_connector_mode": "Offline"
    }


def load_cost_data(client_id=None, as_frame=True):
    try:
        # payload = fetch_cost_data_from_service(client_id)  # Legacy, now removed
        pass
    except Exception:
        logger.exception("Failed to load cost data from the test service layer")
        payload = _default_payload()
        payload["error_message"] = "Failed to load cost data from the test service layer"

    if not as_frame:
        return payload

    return _payload_to_cost_frame(payload, client_id)


def get_last_updated(data=None, client_id=None):
    payload = data if isinstance(data, dict) else load_cost_data(client_id, as_frame=False)
    return payload.get("last_updated") or "Not available"


def get_data_status(data=None, client_id=None):
    payload = data if isinstance(data, dict) else load_cost_data(client_id, as_frame=False)
    return payload.get("source") or "Test Service Layer"


def get_action_data(client_id=None):
    payload = load_cost_data(client_id, as_frame=False)
    return payload.get("actions", [])


def save_action_updates(updated_actions, client_id=None):
    try:
        return save_action_updates_to_service(updated_actions, client_id)
    except Exception:
        logger.exception("Failed to save action updates in the test service layer")
        return False

