# Nexora 2.0.0 Known Limitations and Debt

## Release blockers

Any tracked credential/customer evidence, failed migration, or production fallback to
Demo/development behavior is a blocker. None may be waived as technical debt.

### Required external security action

An archived `.env` removed from HEAD during REL-001 contained non-placeholder PostgreSQL
host, user, and password settings. Its historical validity cannot be proven locally, so it
is classified **POTENTIALLY EXPOSED — ROTATION/REVOCATION REQUIRED**. The associated database
credential and any reused value must be rotated or revoked and access logs reviewed before
production release. Removing it from HEAD does not remove it from Git history; history was
intentionally not rewritten during REL-001.

## Known limitations

- Unsupported evidence types and Ask questions intentionally fail closed.
- Monetary answers require governed currency evidence.
- Universal Evidence SQLite supports single-node deployment; horizontal scaling requires a
  certified shared durable backend.
- Live connectors require provider credentials, permissions, network access, and separate
  source certification.
- Supabase Data Fabric migrations are deployment artifacts, not app-startup migrations.
- Telemetry, workers, billing, AI providers, and scheduled ingestion are optional.

## Technical debt

- Repository-wide Ruff debt: 7,239 legacy findings at ACT-013 closure. It is non-blocking
  while critical syntax, modified-file Ruff, compile, and regression gates stay green.
- Manifests remain split by base, production, frontend, backend, and development roles.
- Historical ACT/PUE and earlier release documents retain their original labels and local
  paths as engineering evidence.

## Future enhancements

- Certified shared lifecycle storage for multi-node deployments.
- Additional governed Ask intents and evidence profiles.
- Broader live connector certification and deployment automation.
- Incremental bounded legacy lint remediation.
