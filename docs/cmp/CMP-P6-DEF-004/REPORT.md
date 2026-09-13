# CMP-P6-DEF-004 - Database Schema Authority Recovery

**Status: HISTORICAL_SCHEMA_AUTHORITY_UNAVAILABLE**

## Boundary

This was a local-only artifact and tooling inventory. No external Supabase,
Nexora validation project, AWS, Azure, client system, staging project, commit,
or push was accessed. No Git archaeology was performed. No application or
schema source files were changed.

## Local artifact inventory

| Artifact | Type | Result |
| --- | --- | --- |
| `.tmp/def001-postgres` | Prior disposable PostgreSQL data directory | Present as a prior certification artifact; not a running historical development database and not reused |
| `cloud_advisor.db` | SQLite file | Present; local SQLite artifact, not evidence of PostgreSQL public schema; rows were not opened |
| `backups/`, `backup_unused/`, archive SQL | Historical SQL/dump material | Present in repository; already classified as evidence/data-bearing history, not safely adoptable as the missing current schema |
| `C:\Users\SrikanthMudaliar\AI-CLOUD-ADVISOR-Backup` | Adjacent backup directory | Directory exists; no project-relevant SQL/dump artifact was returned by the bounded metadata scan |
| `C:\Users\SrikanthMudaliar\AI-Cloud-Advisor_BACKUP` | Adjacent backup directory | Directory exists; no project-relevant SQL/dump artifact was returned by the bounded metadata scan |
| `C:\Users\SrikanthMudaliar\Nexora-P3-docs-backup` | Documentation backup | Documentation only in the bounded scan; no database dump or cluster identified |
| `C:\Users\SrikanthMudaliar\.supabase` | Supabase CLI local state | Telemetry and trace metadata only; no local database volume identified |
| Docker metadata | Docker Desktop state | Installed metadata only; daemon stopped during the first inventory and was not started |

The workspace and project-adjacent searches did not identify a schema-only
Nexora database dump, PostgreSQL custom-format dump, Supabase local volume, or
safe historical export containing the 34 exact unresolved public objects.

## PostgreSQL inventory

Two native Windows PostgreSQL services are running:

- `postgresql-x64-14`, PostgreSQL 14, listening on local port `5433`
- `postgresql-x64-18`, PostgreSQL 18, listening on local port `5432`

Their standard data directories exist under:

- `C:\Program Files\PostgreSQL\14\data`
- `C:\Program Files\PostgreSQL\18\data`

These are live clusters, not disposable certification clusters. Their service
metadata does not establish that either cluster belongs to Nexora or contains
the historical development schema. A catalog-only database-name query was
attempted against loopback, but did not return a usable authenticated result.
No retry, password discovery, authentication bypass, table query, row query,
or schema dump was performed. Therefore no cluster can be called authoritative.

## Supabase-local and Docker inventory

The local Supabase directory contains telemetry/trace metadata but no detected
local database volume or project data directory. Docker Desktop is installed,
but its service/daemon was stopped during discovery. Docker was not started and
its volumes were not inspected through a running daemon. No external service was
touched.

## 34-object comparison

No schema-only extraction was performed: **NO**.

| Comparison result | Count |
| --- | ---: |
| FOUND_EXACT | 0 |
| FOUND_BUT_STALE | 0 |
| FOUND_INCOMPATIBLE | 0 |
| NOT_FOUND / not safely inspectable | 34 |

The prior DEF-003 recovery matrix remains unchanged: all 34 exact active object
contracts remain unresolved. No similarly named connector, mart, approval, or
technology object was treated as an alias.

## Disposable PostgreSQL tooling readiness

The required binaries are available in the native PostgreSQL installations,
although they are not on the current PATH:

- `C:\Program Files\PostgreSQL\14\bin\initdb.exe`, `pg_ctl.exe`, `createdb.exe`, `psql.exe`, `pg_dump.exe`
- `C:\Program Files\PostgreSQL\18\bin\initdb.exe`, `pg_ctl.exe`, `createdb.exe`, `psql.exe`, `pg_dump.exe`

A fresh PostgreSQL 18 certification cluster can therefore be created later in a
new workspace-local temporary directory using explicit binary paths. This
checkpoint did not create or start that cluster. The live service clusters must
not be used for certification.

## Security and artifact checks

- No credentials, client rows, auth users, or secret values were opened or
  copied.
- No external systems were contacted.
- New report credential-pattern scan: PASS.
- `git diff --check`: PASS, with the existing line-ending warning only.
- `git status` was inspected; existing DEF-001/002/003 changes were preserved.

## Decision

**HISTORICAL_SCHEMA_AUTHORITY_UNAVAILABLE**

Git archaeology is complete from DEF-003, and the bounded local artifact search
found no safely inspectable schema authority. The running PostgreSQL clusters
are not identifiable as Nexora without explicit authenticated catalog access,
which was not authorized for this checkpoint and was not completed.

The next authorized program should be **Nexora v1 Current Application Schema
Contract**. It may define new authoritative v1 DDL from the frozen application
contract, clearly labeled as new authority rather than recovered history. Do
not begin that program automatically here.

Commit: **NO**
Push: **NO**
