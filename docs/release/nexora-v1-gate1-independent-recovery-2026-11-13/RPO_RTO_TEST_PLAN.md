# Gate 1 Independent Recovery — RPO/RTO Test Plan

Status: **PROPOSED TARGETS — OWNER ACCEPTANCE REQUIRED; CURRENT PROJECT DRILL
BLOCKED**
No RPO/RTO measurement was made by the engineering-freeze journey or this
fixed-project assessment.

The new PG17 logical-path test verifies compatibility, transactional rollback,
and recovered synthetic service behavior on a disposable container hosted on
the same workstation. It did not record backup/failure/recovery milestone
timestamps, simulate loss of the source host, or restore from an independently
stored artifact. Its pytest duration is not an RTO measurement and provides no
RPO evidence.

## Proposed targets

The existing V1 requirements and recovery record contain no approved RPO or
RTO values. Carry forward these proposals only for owner review:

- **Proposed RPO:** ≤24 hours.
- **Proposed RTO:** ≤4 hours from simulated service failure to application
  availability.

These are not approved SLAs and are not demonstrated. The 24-hour RPO requires
a complete, consistent backup at least daily; the prepared local 03:30 UTC
timer is not installed and does not itself capture PostgreSQL/evidence or copy
data off-host.

## Historical G07 timing is not a measured RTO

The archived G07 record identifies a backup recovery point at
2026-10-17 17:36:05 UTC and a Supabase restore completion record at
2026-10-18 02:11:41 UTC, an elapsed calendar interval of **8 hours 35 minutes
36 seconds**. No restore-start timestamp, simulated service-failure time,
application-available time, or customer-validation completion time is
available. This interval is not restore duration, RPO, or RTO. G07 accepted
database-only coverage and did not certify full application/Auth recovery.

For the fixed project, no execution duration can currently be estimated: no
approved encrypted artifact was retained, its exact size is unknown, the
existing full package rejects PostgreSQL 17.11 for its PostgreSQL 18 source,
and the separate logical path has not been run against the project's actual
roles, schema, Auth, or service configuration. Do not book a recovery window
from the historical interval or local test wall time.

## Measurement definitions

- **RPO** = `simulated_failure` time minus the commit time of the latest
  transaction that is verified in the restored service.
- **RTO** = `simulated_failure` to `application_available`, after database
  restoration, application/Auth configuration, and minimum authenticated
  customer-service checks.
- **Database restore duration** = `recovery_initiated` to
  `database_restore_completed`.
- **Customer validation duration** = `simulated_failure` to
  `customer_validation_completed`.

Report the last two durations separately; do not substitute database restore
time for RTO. The existing measurement utility records the eight UTC events and
reports `rto_seconds`, `database_restore_seconds`, and
`customer_validation_seconds`. It requires timezone-aware timestamps, unique
events, and valid ordering. Use synchronized clocks and preserve the original
JSONL evidence.

## Required event sequence

1. `backup_started`
2. `backup_completed`
3. `last_committed_transaction`
4. `simulated_failure`
5. `recovery_initiated`
6. `database_restore_completed`
7. `application_available`
8. `customer_validation_completed`

Record events through the existing tool only:

```sh
python -m scripts.recovery_measurement record \
  --evidence-file "$NEXORA_RECOVERY_EVIDENCE_FILE" \
  --event backup_started
```

Repeat with each event name and immediately record externally observed UTC
timestamps for milestones not emitted by the command itself. Summarize after
the final event:

```sh
python -m scripts.recovery_measurement summarize \
  --evidence-file "$NEXORA_RECOVERY_EVIDENCE_FILE"
```

The exact package command, transfer, and restore procedure is in
[Recovery Runbook](./RECOVERY_RUNBOOK.md). That runbook explicitly blocks the
current package restore into the historical project; the timing sequence is
for a future separately qualified and authorized recovery path only.

## Acceptance conditions

The drill passes the RPO/RTO gate only if:

1. The owner has accepted or replaced both proposed targets in writing.
2. The package is verified, encrypted, and stored outside the source host and
   failure domain.
3. The last verified commit is no more than 24 hours before the simulated
   failure (or the owner-approved replacement threshold).
4. Authenticated application availability is restored within four hours (or
   the owner-approved replacement threshold).
5. Database restore duration and full customer-validation duration are
   recorded independently; validation confirms synthetic identity, workspace,
   evidence decryption/hash, Ask, decision, Finance/CIO/CEO history,
   evidence-linked export, and Customer B denial.
6. No source or protected project is modified, and the all-in cost stays under
   the authorized ₹1,000 cap.

No timings or actual RPO/RTO values may be inferred from prior pytest wall
time, the local same-host PG17 compatibility run, application restart, backup
creation timing, or the successful engineering-freeze browser journey.

## Final read-only preflight outcome

The catalog-only package
[SUPABASE_READONLY_PREFLIGHT.sql](./SUPABASE_READONLY_PREFLIGHT.sql) is
prepared, but no remote SQL was executed because an authorized read-only
connection and `psql` were unavailable. The fixed database hostname resolved
to IPv6 at 2026-11-13 06:01:04 UTC, which does not establish connectivity.
This preflight therefore adds no backup, failure, restore, or service
availability timestamps. Proposed RPO ≤24 hours and RTO ≤4 hours remain
unaccepted and unmeasured; the independent recovery drill remains blocked.

