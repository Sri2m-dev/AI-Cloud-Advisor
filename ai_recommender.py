# Utility for AI recommendations
from typing import List

import pandas as pd


def generate_recommendations(service_cost: pd.DataFrame) -> List[str]:
    rec: List[str] = []
    top_service = service_cost.iloc[0]["product_product_name"]
    if "EC2" in top_service:
        rec.append("Implement EC2 Savings Plans")
    rec.append("Enable S3 lifecycle policies")
    rec.append("Remove idle EBS volumes")
    rec.append("Rightsize compute workloads")
    return rec
