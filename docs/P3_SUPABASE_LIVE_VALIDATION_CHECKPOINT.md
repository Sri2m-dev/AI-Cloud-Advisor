# P3 Supabase Live-Validation Checkpoint

Status: **PASSED** on the dedicated `nexora-p3-validation` Supabase project (`ageubmyosicypqqkdvox`). No production or `AI-Cloud-Advisor-Dev` access occurred.

## Validated baseline

- Branch: `feature/p3-supabase-live-validation`
- Starting commit: `2daa9e72e9e6d88b1a86d1d60da795187e599e0e`
- Python: 3.11.9
- Migrations: 0001 through 0018 were confirmed pre-applied; the validation did not apply migrations.
- Safety: HTTPS Supabase project-root URL, exact opt-in flag, dedicated credentials, prohibited-target checks, and `p3test-` cleanup scope.

## Required Data API permissions

`service_role` requires `USAGE` on schema `data_fabric`; `SELECT`, `INSERT`, and `DELETE` on `enterprise_entities`; `SELECT` and `INSERT` on `entity_versions`; and `SELECT` on `enterprise_relationships`, `lineage_events`, `provenance_records`, `quality_assessments`, and `idempotency_records`. Atomic mutations use the `EXECUTE` grants established by migrations 0003, 0016, 0017, and 0018. Direct `UPDATE`/`DELETE` remains absent on append-only tables.

## Results

The controlled live suite validates tenant isolation, optimistic concurrency and stale-revision rejection, append-only protection, durable idempotency reservation/completion/replay/failure/expiry, atomic entity create/update/replay/rollback, atomic relationship create/update/replay/rollback, and scoped mutable cleanup. Every created scope uses unique `p3test-` organization, tenant, key, correlation, and source values.

The final atomic suite reports operation counts in pytest output (`P3_ENTITY_COUNTS` and `P3_RELATIONSHIP_COUNTS`). Mutable entities are deleted with exact ID/organization/tenant filters. Relationships are deactivated through migration 0018. Immutable versions, lineage, provenance, quality, and durable idempotency records remain as audit evidence.

Migration 0018 intentionally returns `version_created=false`: relationship-version history is deferred because no compatible persistence contract exists.

## Blockers resolved

Validation initially identified: a non-root `/rest/v1` URL, an unexposed `data_fabric` schema, missing schema `USAGE`, and narrowly missing table `SELECT`/entity mutation privileges. Each boundary failed closed and was resolved by the operator with minimum grants. No automatic grant, RLS, API-setting, migration, or database-object change was made by the validation agent.

One RPC contract edge was recorded: JSON `null` for optional `quality_assessment` is treated as present by migration 0017; callers omit absent optional dependent objects. PostgreSQL rollback was verified complete.

The focused atomic adapter unit module is presently blocked on Python 3.11 by the pre-existing zero-argument `super()` call in frozen slotted persistence dataclasses (`data_fabric/persistence/models.py`). This checkpoint does not alter runtime models or wiring; the safety regressions and direct live RPC suite are the authoritative focused checks for this branch.
