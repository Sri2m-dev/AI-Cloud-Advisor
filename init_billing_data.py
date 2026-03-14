import sqlite3
from datetime import datetime, timedelta
import random

# Connect to the database
conn = sqlite3.connect("cloud_advisor.db")
c = conn.cursor()

# Drop and recreate billing_data table with correct schema
c.execute("DROP TABLE IF EXISTS billing_data")
c.execute("""
CREATE TABLE billing_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    account TEXT,
    service TEXT,
    cost REAL
)
""")

# Generate sample data for the last 90 days
accounts = ["aws-prod", "aws-dev", "azure-main", "gcp-analytics"]
services = ["EC2", "S3", "RDS", "Lambda", "BigQuery", "VM", "Blob Storage", "SQL DB"]
start_date = datetime.now() - timedelta(days=90)

sample_rows = []
for i in range(90):
    day = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
    for account in accounts:
        for service in random.sample(services, 3):
            cost = round(random.uniform(10, 200), 2)
            sample_rows.append((day, account, service, cost))

c.executemany("INSERT INTO billing_data (date, account, service, cost) VALUES (?, ?, ?, ?)", sample_rows)
conn.commit()
conn.close()
print("billing_data table recreated and sample data added.")
