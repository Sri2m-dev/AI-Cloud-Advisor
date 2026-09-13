# Production Configuration Contract

Real values belong in the deployment secret manager, never `.env.example` or Git.

| Name | Purpose | Requirement | Safe default | Production expectation | Secret | Fail-closed behavior |
| --- | --- | --- | --- | --- | --- | --- |
| `ENVIRONMENT` | Runtime policy | Required | `development` | `production` | No | Deployment must set it; production guards depend on this classification |
| `AUTH_MODE` | Authentication backend | Required | dev only | Supabase; never `dev` | No | Local personas disabled outside non-production dev mode |
| `JWT_SECRET` | API token signing | Required | none | High-entropy managed value | Yes | Production token operations raise when absent |
| `SUPABASE_URL` | Tenant datastore/auth endpoint | Required | none | Approved production project | No | Tenant services unavailable; no synthetic fallback |
| `SUPABASE_SERVICE_ROLE_KEY` | Server datastore authority | Required | none | Backend secret manager only | Yes | Production composition does not downgrade to local data |
| `DEFAULT_ORG_ID` | Legacy scoped query default | Conditional | none | Approved tenant where required | No | Missing scope must not select another tenant |
| `NEXORA_UNIVERSAL_EVIDENCE_DB` | Durable lifecycle store | Required | none | Durable backed-up path | Sensitive | Production startup fails before composition |
| `NEXORA_PROSPECT_DATA_ROOT` | Encrypted prospect root | Prospect | `var/prospect_data` | Restricted durable volume | Sensitive | Prospect resume unavailable if storage is unavailable |
| `NEXORA_PROSPECT_DATA_KEY` | Prospect encryption | Prospect | ephemeral outside production | Stable managed Fernet key | Yes | Production persistence raises when absent/invalid |
| `NEXORA_DEMO_MODE` | Demo opt-in | Optional | `false` | `false` in customer production | No | Demo authority unavailable unless Demo tenant is authorized |
| `PUE_PILOT_DEV_MODE` | Development pilot | Optional | `false` | `false` | No | Cannot grant production authority |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Optional OpenAI Responses provider for bounded Ask Nexora generation | Optional | none / `gpt-5.6` | Certified provider/model | Yes/No | Missing key or provider failure raises; no invented evidence; unsupported remains fail-closed |
| `AWS_*`, `AZURE_*`, `GCP_*` | Connector authority | Conditional | none | Workload identity/secret refs preferred | Mixed | Connector unavailable; no simulated success |
| `REDIS_URL`, `CELERY_*` | API/worker state | Conditional | container URL | Managed Redis | Sensitive | Optional API/worker surface unavailable |
| `BACKGROUND_JOBS_ENABLED` | Scheduler activation | Optional | `false` | Explicit after certification | No | Jobs stay off |
| `SCHEDULER_TZ` | Schedule timezone | Optional | `UTC` | Explicit operational zone | No | UTC used |
| `SENTRY_DSN` | Error telemetry | Optional | none | Managed DSN | Yes | Runtime continues without external telemetry |
| `ENABLE_AUDIT_LOGS` | Legacy audit flag | Optional | `true` | `true` | No | Governed UE audit remains independently enforced |
| `CLOUD_ADVISOR_APP_URL`, `STRIPE_SECRET_KEY` | Billing | Conditional | none | Both when billing enabled | Mixed | Billing refuses checkout |

Kill Switch state is durable governed state, not a permissive environment setting. It is
restart-safe and restricted to authorized operations actors.
