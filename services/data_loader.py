import pandas as pd
from shared.queries import get_usage_metrics, get_recommendations
from services.aws_cost import get_aws_cost
from services.azure_cost import get_azure_cost
from services.gcp_cost import get_gcp_cost


def load_all_data(client_id=None):
    usage = get_usage_metrics(client_id)
    reco = get_recommendations()

    aws = get_aws_cost()
    azure = get_azure_cost()
    gcp = get_gcp_cost()

    cost_df = pd.DataFrame(aws + azure + gcp)

    if cost_df.empty:
        cost_df = pd.DataFrame({
            "provider": ["AWS", "AWS"],
            "service": ["EC2", "S3"],
            "cost": [3200, 800]
        })

    # Merge logic (optional later)
    if not usage.empty and "cost" not in usage.columns and "utilization" in usage.columns:
        usage = usage.copy()
        usage["cost"] = usage["utilization"] * 0.5

    return usage, reco, cost_df
