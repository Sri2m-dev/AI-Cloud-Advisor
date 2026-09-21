# Nexora External Pilot Acceptance Checklist

## Certification Identity

- [ ] Nexora release/commit recorded
- [ ] Deployment environment recorded
- [ ] Pilot organization recorded
- [ ] Pilot owner recorded
- [ ] Validation date recorded

## Repository Certification

- [ ] Certified Production Activation baseline used
- [ ] Production compose validates
- [ ] Bootstrap manifest identity validated
- [ ] No unapproved application changes introduced

State:

`REPOSITORY_CERTIFIED = PASS / FAIL`

## Configuration

- [ ] Production environment enabled
- [ ] Demo mode disabled
- [ ] Strong JWT secret configured
- [ ] Runtime environment files excluded from Git
- [ ] Service-role credential backend-only
- [ ] Connector credentials excluded from source control
- [ ] Optional integrations classified correctly

## Database

- [ ] Production bootstrap contract followed
- [ ] Public schema bootstrap complete
- [ ] Enterprise Data Fabric bootstrap complete
- [ ] Universal Evidence lifecycle initialized
- [ ] SourceFacts authority initialized
- [ ] Connector local persistence initialized
- [ ] Backup responsibility confirmed

## Authentication

- [ ] Supabase/Auth environment configured
- [ ] Pilot administrator created/invited
- [ ] Administrator mapped to correct organization
- [ ] Role/persona validated
- [ ] Valid login tested
- [ ] Invalid login tested
- [ ] Logout/session behavior tested
- [ ] Production local-auth bypass unavailable

State:

`APPLICATION_AUTH_CONTRACT = PASS / FAIL`

After authorized live validation only:

`LIVE_AUTH_VALIDATED = PASS / ENVIRONMENT_REQUIRED / FAIL`

## Tenant Isolation

- [ ] Pilot organization is distinct
- [ ] User organization scope validated
- [ ] Cross-tenant access rejected
- [ ] Data Fabric organization boundary validated
- [ ] Universal Evidence organization boundary validated
- [ ] SourceFacts ownership validated
- [ ] Connector ownership validated
- [ ] Ask Nexora evidence scope validated
- [ ] Executive views remain tenant scoped

## Connector

For each pilot connector:

- [ ] Connector name recorded
- [ ] Owning organization recorded
- [ ] Credential source approved
- [ ] Connectivity tested
- [ ] Initial bounded sync completed
- [ ] Failure/error path checked
- [ ] SourceFacts/LiveSource evidence confirmed
- [ ] Lineage/provenance confirmed
- [ ] Downstream Data Fabric processing confirmed
- [ ] Tenant isolation confirmed

After authorized live validation only:

`LIVE_CONNECTOR_VALIDATED = PASS / ENVIRONMENT_REQUIRED / FAIL`

## Ask Nexora

- [ ] Tenant-scoped evidence confirmed
- [ ] Missing-provider behavior confirmed
- [ ] No secret leakage observed
- [ ] Cross-tenant evidence unavailable
- [ ] External AI provider separately validated if enabled

## Runtime

- [ ] Frontend responds
- [ ] Streamlit health responds
- [ ] API health responds
- [ ] Redis healthy
- [ ] Metrics available
- [ ] Logs accessible
- [ ] Database dependency status understood
- [ ] Worker/Beat state explicitly recorded

State:

`LOCAL_RUNTIME_CERTIFIED = PASS / FAIL`

## Backup / Recovery

- [ ] PostgreSQL/Supabase backup owner recorded
- [ ] Universal Evidence backup approach recorded
- [ ] SourceFacts/connector-state recovery understood
- [ ] Secrets excluded from backup artifacts
- [ ] Restore procedure documented/validated as required

## Failure Handling

- [ ] Invalid authentication handled safely
- [ ] Missing connector credentials handled safely
- [ ] Connector sync failure observable
- [ ] AI-provider absence handled safely
- [ ] Database misconfiguration observable
- [ ] Restart behavior validated

## Security

- [ ] No real credentials tracked
- [ ] No private keys tracked
- [ ] No privileged credential exposed to frontend
- [ ] Demo bypass disabled
- [ ] Production local-auth bypass disabled
- [ ] Tenant isolation validated

## Environment Validation

State:

`ENVIRONMENT_VALIDATED = PASS / PENDING / FAIL`

Environment-specific items:

- [ ] Supabase/Auth
- [ ] customer connector(s)
- [ ] AI provider if enabled
- [ ] monitoring/notification integration if enabled
- [ ] DNS/TLS if externally exposed

## Pilot Acceptance

Repository:

`REPOSITORY_CERTIFIED =`

Local runtime:

`LOCAL_RUNTIME_CERTIFIED =`

Application contracts:

`APPLICATION_CONTRACT_CERTIFIED =`

Environment:

`ENVIRONMENT_VALIDATED =`

Live authentication:

`LIVE_AUTH_VALIDATED =`

Live connectors:

`LIVE_CONNECTOR_VALIDATED =`

Production load/SLA:

`NOT_PART_OF_PA004`

Cloud deployment:

`DEFERRED_TO_PA005`

## Final Decision

- [ ] Pilot accepted
- [ ] Pilot accepted with environment dependencies
- [ ] Pilot blocked

Approved by:

Date:

Notes:
