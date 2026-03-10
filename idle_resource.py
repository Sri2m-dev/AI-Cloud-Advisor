def detect_idle_resources(df, service_column, utilization_column):
    insights = []
    if df.empty or not service_column or not utilization_column:
        return insights
    # Filter EC2 instances with low utilization
    ec2_mask = df[service_column].str.contains("Elastic Compute", case=False, na=False)
    low_util = df[utilization_column] < 10
    idle = df[ec2_mask & low_util]
    for _, row in idle.iterrows():
        instance = row.get("InstanceId", "EC2 Instance")
        utilization = row[utilization_column]
        waste = row["Cost_Display"]
        insights.append(f"EC2 instance utilization <10%\nEstimated waste: ${waste:,.0f}/month")
    return insights
