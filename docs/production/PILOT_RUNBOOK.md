# Nexora External Pilot Runbook

## Purpose

This runbook is the operational authority for deploying and validating a
controlled Nexora external pilot from the certified Production Activation
baseline.

It does not certify live customer credentials, live Supabase authentication,
individual customer connectors, production load/SLA, or a particular cloud
hosting platform.

## Certified Baseline

The Production Activation baseline has certified:

- portable Docker production runtime;
- deterministic production database bootstrap;
- public schema and Enterprise Data Fabric bootstrap;
- Universal Evidence local lifecycle;
- SourceFacts local authority;
- local connector persistence;
- production credential separation;
- application authentication contract;
- tenant/organization scoping contract;
- connector-to-evidence architecture;
- health, metrics and operational foundations.

Environment-specific services must be validated for each pilot.

## Architecture

The authoritative Nexora information path is:

Source Systems / Connectors
→ LiveSource / SourceFacts
→ Enterprise Data Fabric
→ Enterprise Registry / Relationship Intelligence
→ Universal Evidence governed workflows
→ Enterprise / Financial / Technology Intelligence
→ Ask Nexora / Decisions
→ Executive Experience

A pilot must use these existing authorities. Do not create parallel ingestion,
evidence, Data Fabric, Knowledge Graph or AI paths.

## 1. Prerequisites

Required:

- Docker and Docker Compose
- certified Nexora source/release
- production environment templates
- production bootstrap manifest
- PostgreSQL/Supabase environment for the production data plane
- pilot organization identity
- authorized pilot administrator

Environment-specific:

- Supabase project
- external connector credentials
- AI provider credentials
- monitoring/notification integrations
- public DNS/TLS/reverse proxy when externally exposed

## 2. Production Configuration

Start from:

- `.env.production.example`
- `.env.production.backend.example`

Never commit populated runtime environment files.

Public/application configuration and privileged backend configuration are
separated intentionally.

`SUPABASE_SERVICE_ROLE_KEY` is backend-only and must never be supplied to the
frontend container.

Required production safety expectations include:

- `ENVIRONMENT=production`
- strong `JWT_SECRET`
- `NEXORA_DEMO_MODE=false`
- production local authentication bypass disabled
- valid Supabase configuration where interactive authentication/data-plane
  functionality is required

Connector/API credentials are added only for capabilities authorized for the
pilot.

## 3. Database Bootstrap

The authoritative bootstrap contract is:

`deploy/production/bootstrap-manifest.json`

Execute only the domains and ordering defined by that manifest.

The certified contract contains:

1. public PostgreSQL bootstrap
2. dated public migrations
3. Enterprise Data Fabric migrations
4. Universal Evidence local lifecycle
5. SourceFacts local authority
6. Live Connector local persistence

Steps 4-6 are application/local lifecycle domains and must not be incorrectly
replayed as PostgreSQL migrations.

Historical backups and standalone SQL files are not automatically part of the
production migration authority.

## 4. Supabase and Authentication

Production interactive UI authentication uses Supabase Auth.

For an external pilot:

1. provision the authorized Supabase environment;
2. configure public URL/public key for the application;
3. configure privileged service-role credentials only for backend services;
4. create or invite the pilot administrator using the supported onboarding
   path;
5. associate the user with the correct organization;
6. assign the required role/persona;
7. test successful login;
8. test invalid login;
9. test logout/session handling;
10. verify another organization cannot be accessed.

Repository/local certification proves the application authentication contract.
The actual Supabase project must be validated separately.

## 5. Organization Onboarding

For every pilot create a distinct organization boundary.

Validate:

- organization identity;
- administrator/user membership;
- role/persona assignment;
- organization-scoped repositories/services;
- Data Fabric organization isolation;
- Universal Evidence isolation;
- SourceFacts ownership;
- connector ownership;
- executive experience isolation;
- Ask Nexora evidence isolation.

Never reuse another customer's organization as a shortcut.

## 6. Connector Onboarding

Enable only connectors approved for the pilot.

For each connector:

1. identify the owning organization;
2. configure credentials outside source control;
3. validate connectivity;
4. perform a bounded initial sync;
5. verify error handling;
6. verify SourceFacts/LiveSource evidence creation;
7. verify lineage/provenance;
8. verify downstream Data Fabric processing;
9. verify organization isolation;
10. record the connector as LIVE_VALIDATED only after an authorized live test.

Synthetic/local connector certification must not be represented as live
customer-connector certification.

## 7. Ask Nexora

Ask Nexora must remain tenant/evidence scoped.

Where an external AI provider is configured, validate the authorized provider
and credential separately.

Without the required AI provider configuration, AI-assisted functionality may
remain environment-dependent; this must not be confused with failure of the
core production runtime.

Never expose secrets or another organization's evidence to prompts or output.

## 8. Start and Validate Runtime

Validate the production compose contract before startup:

`docker compose -f docker-compose.production.yml config`

Expected core runtime:

- redis
- api
- frontend
- nginx

Worker/Beat must be enabled only when the approved production scheduling
authority is established for the deployment.

Validate:

- frontend response
- Streamlit health
- API health
- metrics
- logs
- dependency configuration

## 9. Health and Observability

Pilot operations must verify:

- frontend availability;
- API health;
- Redis health;
- database dependency;
- metrics;
- application logs;
- connector sync failures;
- authentication failures;
- background-job state.

A process being alive does not by itself certify external dependencies.

## 10. Backup and Recovery

The deployment owner must define and validate backup responsibility for:

- PostgreSQL/Supabase;
- Universal Evidence persistent storage;
- SourceFacts/local connector state where applicable;
- required deployment configuration.

Secrets must not be included in source-controlled backup artifacts.

Recovery must be tested using authorized disposable/non-production data before
being represented as production recovery certification.

## 11. Pilot Validation

A pilot is accepted only when the accompanying
`PILOT_ACCEPTANCE_CHECKLIST.md` has been completed.

Repository/local certification and live-environment certification are separate
states.

Do not mark the following as validated without an authorized live test:

- LIVE_SUPABASE_AUTH
- LIVE_CUSTOMER_CONNECTORS
- external AI provider
- external notification integrations
- production load/SLA

## 12. Troubleshooting

When onboarding fails, classify the failure before changing code:

- application defect;
- configuration;
- credential/permission;
- external provider;
- customer environment;
- network;
- database/bootstrap;
- connector-specific issue.

Do not modify certified architecture to compensate for an environment-specific
configuration problem.

## 13. Rollback

For application rollback:

1. stop the affected deployment safely;
2. preserve required evidence/logs;
3. restore the previously certified application release;
4. restore database/data only according to the approved recovery procedure;
5. validate health and tenant boundaries;
6. document the rollback reason.

Never downgrade a database blindly across irreversible migrations.

## 14. Pilot Cleanup

At pilot completion:

- revoke pilot connector credentials;
- revoke pilot-only users where required;
- remove temporary access;
- retain/delete pilot data according to the agreed retention policy;
- remove temporary infrastructure;
- verify secrets are not retained in source control or logs;
- record the final pilot disposition.

## 15. Certification States

Use these states explicitly:

- `REPOSITORY_CERTIFIED`
- `LOCAL_RUNTIME_CERTIFIED`
- `APPLICATION_CONTRACT_CERTIFIED`
- `ENVIRONMENT_VALIDATED`
- `LIVE_AUTH_VALIDATED`
- `LIVE_CONNECTOR_VALIDATED`

A lower certification state must never be described as a higher one.

## Deferred Production Activities

The following remain environment/deployment-specific:

- live Supabase authentication validation;
- live customer connector validation;
- production load/SLA validation;
- cloud deployment architecture and infrastructure.

Cloud deployment is handled separately under PA-005 when required.
