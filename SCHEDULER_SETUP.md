# APScheduler Configuration - Complete Setup

## Overview

**APScheduler** is configured for background job automation. All jobs run on fixed schedules specified by interval or cron triggers.

**Status**: ✅ **ACTIVE** - Scheduler starts automatically when FastAPI backend initializes with `BACKGROUND_JOBS_ENABLED=true`

---

## Enabled Jobs & Schedule

| Job | Frequency | Purpose | Engine |
|-----|-----------|---------|--------|
| `cost_ingestion_hourly` | Every 1h | Ingest cost data from cloud providers | Backend |
| `anomaly_scan_hourly` | Every 1h | Detect cost anomalies | Backend |
| `alert_engine_hourly` | Every 1h | Trigger legacy alert engine | Backend |
| **`escalation_hourly`** ⭐ | Every 1h | **SLA violation detection & escalation** | **escalation_service** |
| **`alert_processor_hourly`** ⭐ | Every 1h | **Route escalations to multi-channel alerts** | **alert_processor** |
| `kpi_refresh_15m` | Every 15min | Refresh dashboard KPIs | Backend |
| `optimization_engine_daily` | Daily @ 2 AM | Generate optimization recommendations | Backend |
| `report_generation_daily` | Daily @ 3 AM | Generate daily reports | Backend |

**⭐ New Jobs** (Part of Workflow Governance Architecture):
- **escalation_hourly**: Calls `batch_escalate_stale()` for PENDING_APPROVAL (48h SLA) and APPROVED (72h SLA)
- **alert_processor_hourly**: Sends multi-channel alerts (email, Slack, Teams, webhooks) for recent escalations

---

## Configuration

### Enable/Disable Scheduler

**Environment Variable**: `BACKGROUND_JOBS_ENABLED`

```bash
# Enable scheduler on startup
export BACKGROUND_JOBS_ENABLED=true

# Disable (scheduler won't start)
export BACKGROUND_JOBS_ENABLED=false
```

**Backend Entry Point** (`backend/main.py`):
```python
@app.on_event("startup")
def startup_jobs() -> None:
    if os.getenv("BACKGROUND_JOBS_ENABLED", "false").lower() == "true":
        start_scheduler()

@app.on_event("shutdown")
def shutdown_jobs() -> None:
    stop_scheduler()
```

### Timezone Configuration

**Environment Variable**: `SCHEDULER_TZ`

```bash
# Default: UTC
export SCHEDULER_TZ=UTC

# Other examples
export SCHEDULER_TZ=America/New_York
export SCHEDULER_TZ=Europe/London
export SCHEDULER_TZ=Asia/Tokyo
```

---

## Architecture

### File Structure

```
backend/
├── jobs/
│   ├── scheduler.py          ← APScheduler initialization & job registration
│   ├── tasks.py              ← Job implementations (8 jobs)
│   └── __init__.py
├── main.py                   ← FastAPI app with startup/shutdown events
└── celery_app.py             ← Celery integration (optional, for distributed jobs)

services/
├── escalation_service.py     ← SLA enforcement engine
└── alert_processor.py        ← Multi-channel alert orchestrator
```

### Data Flow

```
1. APScheduler fires job at configured interval
   ↓
2. Job function executes (e.g., escalation_hourly)
   ↓
3. Service layer performs business logic
   ├─ escalation_service.batch_escalate_stale()
   │  └─ Identifies stale items, transitions to ESCALATED state
   │  └─ Records events in recommendation_events table
   │
   └─ alert_processor.process_alerts()
      └─ Queries alert_configs table
      └─ Routes to Slack/Email/Teams/Webhook engines
      └─ Records execution in alert_executions table
   ↓
4. Results logged with [scheduler] tag for debugging
```

---

## Key Features

### 1. **Coalesce & Max Instances**
Each job has:
- `coalesce=True`: Skip missed runs if scheduler was temporarily down
- `max_instances=1`: Prevent duplicate concurrent execution

**Benefit**: Safe to restart scheduler without job stacking

### 2. **Logging**
All scheduler activities logged with `[scheduler]` prefix:
```
[scheduler] escalation_hourly: Starting...
[scheduler] escalation_hourly: PENDING_APPROVAL - escalated 3
[scheduler] escalation_hourly: APPROVED - escalated 1
[scheduler] alert_processor_hourly: Processed 4 escalations
```

### 3. **Error Handling**
- Each job wraps logic in try-except
- Failures logged but don't crash scheduler
- Scheduler continues executing remaining jobs

---

## Escalation & Alert Flow

### Escalation Job (Hourly)

```python
job_escalation_hourly():
  1. Find PENDING_APPROVAL items created >48 hours ago
  2. Find APPROVED items created >72 hours ago
  3. For each stale item:
     - Validate SLA violation
     - Transition to ESCALATED state
     - Log event in recommendation_events
     - Queue notification
  4. Return { escalated_count, failed_count }
```

### Alert Processor Job (Hourly)

```python
job_alert_processor_hourly():
  1. Query recommendation_events for past hour
  2. Filter for escalation events only
  3. If escalations found:
     - Get active alert configs from DB
     - Call process_alerts() to route to channels:
       ├─ Email (SMTP)
       ├─ Slack (webhook)
       ├─ Microsoft Teams (webhook)
       └─ Generic Webhook
  4. Record all executions in alert_executions table
```

---

## Database Tables Used

### `alert_configs`
Stores alert channel configurations

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| channel | string | 'email' \| 'slack' \| 'teams' \| 'webhook' |
| active | bool | Enable/disable config |
| webhook_url | string | For Slack/Teams/Webhook |
| recipients | array | Email addresses |
| slack_channel | string | Target Slack channel |
| include_metadata | bool | Attach additional context |

**Setup Required**: Register at least 1 active config per channel you want to use

### `alert_executions`
Audit trail of all alerts sent

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| config_id | int | FK to alert_configs |
| channel | string | 'email' \| 'slack' \| 'teams' \| 'webhook' |
| title | string | Alert subject |
| message | string | Alert body |
| severity | string | 'critical' \| 'warning' \| 'info' |
| success | bool | Did send succeed? |
| error_message | string | Error details if failed |
| executed_at | timestamp | When sent |

**Query**: `SELECT * FROM alert_executions WHERE executed_at > now() - interval '1 hour' ORDER BY executed_at DESC`

### `recommendation_events`
Workflow history and escalation events

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| recommendation_id | int | FK to recommendations |
| event_type | string | 'escalation' \| 'transition' \| 'comment' |
| actor | string | Who triggered event (user or 'scheduler_system') |
| old_state | string | Previous workflow state |
| new_state | string | New workflow state |
| notes | string | Event metadata |
| created_at | timestamp | Event time |

---

## Environment Variables (Complete)

**Scheduler Control**:
```bash
BACKGROUND_JOBS_ENABLED=true           # Enable/disable
SCHEDULER_TZ=UTC                        # Timezone for cron jobs
```

**Email (SMTP)**:
```bash
ALERT_SMTP_SERVER=smtp.gmail.com
ALERT_SMTP_PORT=587
ALERT_SMTP_USERNAME=your-email@gmail.com
ALERT_SMTP_PASSWORD=your-app-password
ALERT_SMTP_FROM=alerts@yourcompany.com
```

**Slack**:
```bash
# Register webhook URLs in alert_configs table instead
```

**Microsoft Teams**:
```bash
# Register webhook URLs in alert_configs table instead
```

---

## Testing & Monitoring

### 1. **View Scheduler Jobs**

**API Endpoint**: GET `/health`

```bash
curl http://localhost:8000/health
# Returns: {"status": "ok"}
```

### 2. **Manually Test Escalation**

**API Endpoint**: POST `/api/v1/escalations/trigger`

```bash
curl -X POST http://localhost:8000/api/v1/escalations/trigger \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_state": "PENDING_APPROVAL",
    "dry_run": false
  }'

# Response:
# {
#   "ok": true,
#   "escalated_count": 2,
#   "total_checked": 5,
#   "message": "2 items escalated (3 not stale)"
# }
```

### 3. **View Escalation Report**

**API Endpoint**: GET `/api/v1/escalations/report`

```bash
curl http://localhost:8000/api/v1/escalations/report?days=7 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Returns escalations from past 7 days with counts by state
```

### 4. **View Alert Execution History**

**API Endpoint**: GET `/api/v1/alerts/v2/executions`

```bash
curl http://localhost:8000/api/v1/alerts/v2/executions?limit=20 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Returns:
# {
#   "ok": true,
#   "executions": [
#     {
#       "id": 42,
#       "channel": "slack",
#       "success": true,
#       "executed_at": "2026-05-16T14:32:10.123Z"
#     },
#     ...
#   ]
# }
```

### 5. **Send Test Alert**

**API Endpoint**: POST `/api/v1/alerts/v2/send`

```bash
curl -X POST http://localhost:8000/api/v1/alerts/v2/send \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Alert",
    "message": "This is a test alert from APScheduler",
    "severity": "warning"
  }'

# Routes to all active alert configs
```

---

## Quick Start Checklist

- [ ] **Enable scheduler**: Set `BACKGROUND_JOBS_ENABLED=true` in environment
- [ ] **Configure email** (optional): Set ALERT_SMTP_* env vars
- [ ] **Register alert configs**: Insert rows into `alert_configs` table with:
  - Slack webhook URL(s)
  - Teams webhook URL(s)
  - Email recipient(s)
  - Webhook endpoint(s)
- [ ] **Start backend**: `python -m backend.main` or via Docker
- [ ] **Test escalation**: POST `/api/v1/escalations/trigger?dry_run=true`
- [ ] **Monitor logs**: Look for `[scheduler]` entries
- [ ] **Verify alerts**: Check `alert_executions` table for sent alerts

---

## Troubleshooting

### "Scheduler not running"

**Check**:
1. Verify `BACKGROUND_JOBS_ENABLED=true` is set
2. Check logs for `Background scheduler started with X jobs`
3. Ensure FastAPI startup event completed successfully

### "Jobs not firing"

**Check**:
1. Verify timezone in `SCHEDULER_TZ` matches your region
2. Use `GET /api/v1/escalations/report` to see if escalations are being created
3. Check job logs with `[scheduler]` prefix

### "Alerts not sending"

**Check**:
1. Verify at least 1 active config in `alert_configs` table
2. Test specific config: POST `/api/v1/alerts/v2/test` with `config_id`
3. Check `alert_executions` table for error messages
4. For email: verify SMTP credentials and firewall rules

### "Job running too long or failing"

**Check**:
1. Logs will show job start/end with execution time
2. If job fails, error message logged with full stacktrace
3. Next run will execute normally (coalesce handles skipped runs)
4. Increase interval if job is compute-heavy

---

## Production Recommendations

1. **Monitor scheduler health**: Add metrics export for job execution times
2. **Set up alerting**: Alert if jobs fail or exceed expected duration
3. **Use external Redis**: For Celery integration with task persistence
4. **Log aggregation**: Centralize logs with ELK stack or similar
5. **Load testing**: Test alert processor with high escalation volume
6. **Backup DB**: Ensure `alert_configs` table is backed up
7. **Timezone consistency**: Use UTC consistently across deployments

---

## Integration with Celery

For distributed deployments, the same jobs can be registered as Celery tasks:

```python
# backend/celery_tasks.py
@celery_app.task(name="backend.celery_tasks.job_escalation_hourly_task")
def job_escalation_hourly_task():
    job_escalation_hourly()

@celery_app.task(name="backend.celery_tasks.job_alert_processor_hourly_task")
def job_alert_processor_hourly_task():
    job_alert_processor_hourly()
```

**Benefits**:
- Distribute jobs across multiple worker nodes
- Retry failed jobs automatically
- Persist job history
- Monitor via Flower dashboard

**Trade-off**: Requires Redis + Celery workers (more complex)

---

## Summary

✅ **APScheduler active** with 8 jobs registered
✅ **Escalation engine** running hourly to detect SLA violations
✅ **Alert processor** running hourly to send multi-channel notifications
✅ **Full audit trail** in `alert_executions` and `recommendation_events` tables
✅ **API endpoints** for manual testing and configuration

**Next Steps**:
1. Configure alert channels (Slack webhooks, email, Teams, etc.)
2. Enable scheduler in environment: `BACKGROUND_JOBS_ENABLED=true`
3. Monitor escalation and alert execution via API and DB tables
