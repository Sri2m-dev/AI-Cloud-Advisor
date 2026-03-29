import pandas as pd

def architecture_optimization(df):
    """Suggest architecture improvements based on service type."""
    suggestions = []
    for _, row in df.iterrows():
        service = row.get("service", "")
        if service == "EC2":
            suggestions.append("EC2: Move to Graviton")
        elif service == "RDS":
            suggestions.append("RDS: Enable storage autoscaling")
        elif service == "S3":
            suggestions.append("S3: Apply lifecycle policy")
        elif service == "EKS":
            suggestions.append("EKS: Use Spot nodes")
    return suggestions
