#!/usr/bin/env python
"""
Quick Start: APScheduler Automation
Run this guide to get the scheduler running and test it.
"""

import subprocess
import os
import sys


def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def main():
    print_section("AI Cloud Advisor - APScheduler Quick Start")

    # Step 1: Environment check
    print("STEP 1: Check Environment Variables")
    print("-" * 70)

    required_vars = {
        "BACKGROUND_JOBS_ENABLED": "Enable scheduler (true/false)",
        "SCHEDULER_TZ": "Timezone for daily jobs (e.g., UTC)",
    }

    optional_vars = {
        "ALERT_SMTP_SERVER": "Email: SMTP server",
        "ALERT_SMTP_PORT": "Email: SMTP port (usually 587)",
        "ALERT_SMTP_USERNAME": "Email: username/sender address",
        "ALERT_SMTP_PASSWORD": "Email: password",
        "ALERT_SMTP_FROM": "Email: from address",
    }

    print("\nREQUIRED:")
    for var, desc in required_vars.items():
        value = os.getenv(var, "[NOT SET]")
        status = "✓" if value != "[NOT SET]" else "✗"
        print(f"  {status} {var:35} = {value:30} ({desc})")

    print("\nOPTIONAL (for email alerts):")
    for var, desc in optional_vars.items():
        value = os.getenv(var, "[NOT SET]")
        status = "✓" if value != "[NOT SET]" else "○"
        # Hide passwords
        if "PASSWORD" in var and value != "[NOT SET]":
            value = "*" * 16
        print(f"  {status} {var:35} = {value:30} ({desc})")

    print("\n📝 To configure: Copy .env.scheduler.template to .env.local and edit")

    # Step 2: Dependencies
    print_section("STEP 2: Check Dependencies")
    print("-" * 70)

    deps = ["apscheduler", "fastapi", "supabase"]
    missing = []

    for dep in deps:
        try:
            __import__(dep)
            print(f"  ✓ {dep:20} installed")
        except ImportError:
            print(f"  ✗ {dep:20} MISSING")
            missing.append(dep)

    if missing:
        print(f"\n⚠️  Install missing: pip install {' '.join(missing)}")
    else:
        print("\n✓ All dependencies installed")

    # Step 3: Database
    print_section("STEP 3: Database Tables")
    print("-" * 70)

    tables_needed = [
        ("alert_configs", "Alert channel configurations"),
        ("alert_executions", "Alert execution audit trail"),
        ("recommendation_events", "Workflow history & escalations"),
        ("recommendations", "Workflow items"),
    ]

    print("\nRequired tables:")
    for table, desc in tables_needed:
        print(f"  □ {table:30} - {desc}")

    print("\n📝 To check: Query your Supabase database for these tables")
    print("   Run migrations if tables are missing")

    # Step 4: Configuration
    print_section("STEP 4: Configure Alert Channels")
    print("-" * 70)

    print("""
To enable multi-channel alerts, register configurations in alert_configs table:

Example SQL:
-----------
-- Email alerts
INSERT INTO alert_configs (name, channel, active, recipients, created_by)
VALUES ('Admin Email', 'email', true, ARRAY['admin@example.com'], 'system');

-- Slack alerts
INSERT INTO alert_configs (name, channel, active, webhook_url, created_by)
VALUES ('Slack DevOps', 'slack', true, 
  'https://hooks.slack.com/services/T.../B.../...', 'system');

-- Microsoft Teams alerts
INSERT INTO alert_configs (name, channel, active, webhook_url, created_by)
VALUES ('Teams Ops', 'teams', true,
  'https://outlook.webhook.office.com/webhookb2/...', 'system');

-- Custom webhooks
INSERT INTO alert_configs (name, channel, active, webhook_url, created_by)
VALUES ('Custom Endpoint', 'webhook', true,
  'https://your-api.example.com/alerts', 'system');

To verify:
----------
SELECT id, name, channel, active FROM alert_configs WHERE active = true;
""")

    # Step 5: Start scheduler
    print_section("STEP 5: Start the Scheduler")
    print("-" * 70)

    print("""
Option A: Via FastAPI Backend (Recommended)
--------------------------------------------
$ python -m backend.main
  - Scheduler auto-starts if BACKGROUND_JOBS_ENABLED=true
  - API available at http://localhost:8000

Option B: Standalone Scheduler (Local Testing)
-----------------------------------------------
$ python scheduler.py
  - Runs 5 sample jobs
  - Ctrl+C to stop
  - Good for development/testing

Option C: Via Docker Compose
------------------------------
$ docker-compose up -d backend
  - Scheduler runs inside container
  - Check logs: docker-compose logs backend
""")

    # Step 6: Test
    print_section("STEP 6: Test the Scheduler")
    print("-" * 70)

    print("""
Test Escalation (detect SLA violations):
-----------------------------------------
$ curl -X POST http://localhost:8000/api/v1/escalations/trigger \\
    -H "Authorization: Bearer YOUR_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{"workflow_state": "PENDING_APPROVAL", "dry_run": true}'

Expected response:
{
  "ok": true,
  "escalated_count": 0,
  "total_checked": 5,
  "message": "0 items escalated (5 not stale)"
}

Test Alerts (send to all configured channels):
-----------------------------------------------
$ curl -X POST http://localhost:8000/api/v1/alerts/v2/send \\
    -H "Authorization: Bearer YOUR_TOKEN" \\
    -H "Content-Type: application/json" \\
    -d '{
      "title": "Test Alert",
      "message": "This is a test alert from the scheduler",
      "severity": "warning"
    }'

Expected response:
{
  "ok": true,
  "total_sent": 2,
  "total_failed": 0,
  "by_channel": {
    "slack": 1,
    "email": 1
  }
}

View Alert History:
--------------------
$ curl http://localhost:8000/api/v1/alerts/v2/executions?limit=10 \\
    -H "Authorization: Bearer YOUR_TOKEN"

Check Escalation Report:
------------------------
$ curl http://localhost:8000/api/v1/escalations/report?days=7 \\
    -H "Authorization: Bearer YOUR_TOKEN"
""")

    # Step 7: Monitor
    print_section("STEP 7: Monitor Scheduler")
    print("-" * 70)

    print("""
Watch Logs (Look for [scheduler] entries):
-------------------------------------------
$ tail -f backend.log | grep scheduler

Database Queries:
-----------------
-- Recent alert executions (past hour)
SELECT channel, count(*), sum(case when success then 1 else 0 end) as sent
FROM alert_executions
WHERE executed_at > now() - interval '1 hour'
GROUP BY channel;

-- Escalation history (past 24 hours)
SELECT workflow_state, event_type, count(*)
FROM recommendation_events
WHERE event_type = 'escalation'
  AND created_at > now() - interval '24 hours'
GROUP BY workflow_state, event_type;

-- Failed alerts (need investigation)
SELECT id, channel, error_message, executed_at
FROM alert_executions
WHERE success = false
ORDER BY executed_at DESC
LIMIT 10;
""")

    # Step 8: Production
    print_section("STEP 8: Production Setup")
    print("-" * 70)

    print("""
For production deployments:

1. Secrets Management
   - Store ALERT_SMTP_* in environment or secrets manager
   - Never commit credentials to git
   - Use strong, randomly generated passwords

2. Monitoring
   - Export metrics: /metrics endpoint for Prometheus
   - Track job execution duration and failure rates
   - Alert if jobs fail or take too long

3. Scaling (optional)
   - Use Celery + Redis for distributed job execution
   - Run multiple workers for fault tolerance
   - Use Flower dashboard for monitoring

4. Logging
   - Aggregate logs to centralized system (ELK, Splunk, etc.)
   - Set LOG_LEVEL=INFO for production
   - Archive logs for compliance

5. Backup
   - Regular backups of alert_configs table
   - Backup recommendation_events for audit trail
   - Test restore procedures

6. Testing
   - Load test alert processor with high volumes
   - Test email/Slack delivery reliability
   - Verify escalation timing accuracy

See SCHEDULER_SETUP.md for complete documentation
""")

    print_section("Summary")
    print("""
✓ Scheduler configured with 8 background jobs
✓ Escalation detection: Hourly SLA checks
✓ Alert routing: Slack, Email, Teams, Webhooks
✓ Full audit trail: All executions tracked
✓ API endpoints: Manual testing and monitoring

🚀 Ready to Deploy!

Next steps:
1. Set BACKGROUND_JOBS_ENABLED=true
2. Configure alert_configs table with your channels
3. Start backend: python -m backend.main
4. Test: POST /api/v1/alerts/v2/send
5. Monitor: Check logs and alert_executions table

Questions? See SCHEDULER_SETUP.md or backend/jobs/scheduler.py
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())

