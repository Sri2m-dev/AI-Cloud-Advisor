import pandas as pd

def detect_resource_waste(df):
    insights = []
    # Idle EC2: EC2 with low cost (proxy for low usage)
    ec2 = df[df['Service'].str.contains('EC2', case=False, na=False)]
    if not ec2.empty:
        for _, row in ec2.iterrows():
            if row['Cost_Display'] < 100:  # Threshold for idle
                insights.append(f"Idle EC2 detected: {row['Service']} (${row['Cost_Display']:,.0f})")
    # Unused EBS: EBS with low cost (proxy for unattached)
    ebs = df[df['Service'].str.contains('EBS', case=False, na=False)]
    if not ebs.empty:
        for _, row in ebs.iterrows():
            if row['Cost_Display'] < 10:
                insights.append(f"Unused EBS volume: {row['Service']} (${row['Cost_Display']:,.0f})")
    # Over-provisioned RDS: RDS with high cost (proxy for over-provisioned)
    rds = df[df['Service'].str.contains('RDS', case=False, na=False)]
    if not rds.empty:
        for _, row in rds.iterrows():
            if row['Cost_Display'] > 10000:
                insights.append(f"Over-provisioned RDS: {row['Service']} (${row['Cost_Display']:,.0f})")
    return insights
