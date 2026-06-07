# Deployment Architecture

## Recommended Stack

| Layer | Technology |
| --- | --- |
| Frontend | Streamlit |
| API | FastAPI |
| DB | Supabase / Postgres |
| Cache | Redis |
| Jobs | Celery |
| Hosting | AWS ECS / Fargate |
| Reverse Proxy | NGINX |
| Monitoring | Grafana + Prometheus |

## Production Topology

- `frontend`: Streamlit container serving the executive dashboard.
- `api`: FastAPI container exposing `/api/v1/*`, `/health`, and `/metrics`.
- `worker`: Celery worker for async jobs and automation.
- `beat`: Celery beat scheduler for periodic jobs.
- `redis`: shared broker and cache for Celery and token/state workloads.
- `nginx`: public entrypoint routing `/` to Streamlit and `/api/` to FastAPI.
- `prometheus`: scrapes API metrics.
- `grafana`: dashboards for API latency, alert throughput, and job health.
- `supabase`: managed Postgres/auth/data plane outside the ECS cluster.

## AWS ECS / Fargate Layout

- Internet-facing ALB -> NGINX service
- NGINX -> Streamlit service + FastAPI service
- Celery worker service (private subnets)
- Celery beat service (private subnets)
- ElastiCache Redis (private subnets)
- Supabase remains managed externally
- CloudWatch logs for all ECS tasks
- Secrets Manager / SSM for runtime secrets

## Files Added

- `Dockerfile.frontend`
- `Dockerfile.api`
- `Dockerfile.worker`
- `Dockerfile.beat`
- `docker-compose.deploy.yml`
- `deploy/nginx/nginx.conf`
- `deploy/prometheus/prometheus.yml`
- `deploy/grafana/provisioning/datasources/prometheus.yml`
- `deploy/ecs/task-api.json`
- `deploy/ecs/task-frontend.json`
- `deploy/ecs/task-worker.json`

## Environment Variables

Minimum runtime secrets/settings:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_SENDER`
- `OPENAI_API_KEY`

## Deployment Notes

- Use Celery for production job execution instead of in-process APScheduler where possible.
- Set `BACKGROUND_JOBS_ENABLED=false` on API tasks when Celery beat is active.
- Keep Redis private; do not expose it publicly.
- Route external traffic through ALB -> NGINX only.
- Scrape FastAPI metrics from `/metrics`.
- Apply Supabase SQL files before go-live:
  - `supabase/tenant_rls_policies.sql`
  - `supabase/reporting_tables.sql`
  - `supabase/alerting_tables.sql`

## Local Production-Style Run

```bash
docker compose -f docker-compose.deploy.yml up --build
```

## Next Hardening Steps

- Add ECS service definitions / Terraform or CloudFormation
- Add ALB health checks and autoscaling policies
- Add Grafana dashboards and alert rules
- Add managed Prometheus / AMP integration
- Add Sentry or OpenTelemetry for traces
