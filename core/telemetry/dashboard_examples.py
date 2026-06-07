from core.telemetry.metrics import MetricsCollector
from typing import Dict

# Example: Record API latency
MetricsCollector.record_metric('api_latency', 0.123, labels={'endpoint': '/api/approve'})

# Example: Record dashboard load time
MetricsCollector.record_metric('dashboard_load_time', 1.45, labels={'page': 'Executive_Dashboard'})

# Example: Record failed workflow
MetricsCollector.record_metric('failed_workflow', 1, labels={'workflow': 'approval'})

# Example: Record query execution time
MetricsCollector.record_metric('query_execution', 0.32, labels={'query': 'fetch_approvals'})

# Example: Record ingestion failure
MetricsCollector.record_metric('ingestion_failure', 1, labels={'source': 'aws_cost'})

# Example: Record user activity
MetricsCollector.record_metric('user_activity', 1, labels={'user_id': 'user1'})

# Example: Retrieve metrics for dashboard
api_latencies = MetricsCollector.get_metrics('api_latency', labels={'endpoint': '/api/approve'})
dashboard_loads = MetricsCollector.get_metrics('dashboard_load_time', labels={'page': 'Executive_Dashboard'})

