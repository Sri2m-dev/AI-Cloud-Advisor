# Nexora v1 — Final Release / Project Closure Record

Date: 2026-09-12
REL-C1 closure update: 2026-09-13

This is the single authoritative record of the certified final state for the
commercial release named **Nexora v1**. It supersedes prior release-status
documents for the purpose of the current commercial-release decision only.
Historical DEF/SC/RC/PUE/CMP certification records are preserved unchanged as
historical evidence and are not rewritten by this document.

```
PROJECT=NEXORA
COMMERCIAL_RELEASE=NEXORA v1

PRODUCT_DEVELOPMENT=CLOSED
PRODUCT_CAPABILITY=COMPLETE_FROZEN
UNIVERSAL_ASK_NEXORA=CERTIFIED_FROZEN
INTEGRATED_UAT=CERTIFIED_FROZEN
REPOSITORY_CERTIFICATION=PASS

FINAL_REGRESSION=
1919 passed
1 known non-blocking failure
2 skipped

KNOWN_NON_BLOCKING_ISSUE=
tests/test_persona_authentication.py::test_all_canonical_personas_seed_and_authenticate
non-production canonical persona organization-ID mismatch; not reachable in
production authentication and does not affect tenant isolation or role
authorization.

OUTSTANDING_PRODUCT_DEFECTS=
NONE_IDENTIFIED

SUPABASE_LIVE_CERTIFICATION=
DEFERRED_EXTERNAL

AWS_LIVE_CERTIFICATION=
DEFERRED_EXTERNAL

AZURE_LIVE_CERTIFICATION=
DEFERRED_EXTERNAL

REL_C1=
PASS_WITH_RECORDED_RESIDUAL_OBSERVATION

COMMERCIAL_RELEASE_STATUS=
READY_FOR_FINAL_RELEASE_STAGING
```

## Recertification condition

Another product certification cycle is required only if the certified
product or repository implementation is subsequently changed. This record
does not need to be regenerated merely because REL-C1 evidence is later
attached; REL-C1 closure updates the REL-C1 section below only.

## Version / release name mapping

- Commercial release name: **Nexora v1**
- Existing internal release lineage: **REL-001 / 2.0.0** (see
  `docs/release/REL_001_RELEASE_CANDIDATE.md`)

This is a release-name/lineage mapping only. No runtime or version metadata
was changed by this document.

## REL-C1 final security closure

Status: **PASS_WITH_RECORDED_RESIDUAL_OBSERVATION**

This closure records the authoritative evidence supplied by project owner
Srikanth on 2026-09-13. It is project-owner risk acceptance for the Nexora
**development project**, not independent corporate Security/InfoSec approval.
No connection, credential verification, log investigation, or product
certification was rerun as part of this documentation update.

### Remediation and verification evidence

```
AFFECTED_SYSTEM=Supabase AI-Cloud-Advisor-Dev
PROJECT_REF=iafrrtmvvqmuksvprrsj
ENVIRONMENT_CLASSIFICATION=Development
HISTORICAL_ISSUE=Previously exposed/hard-coded PostgreSQL credential
ORIGINAL_REPOSITORY_EXPOSURE_DATE=2026-06-07
DATABASE_CREDENTIAL_CONTRACT=PGPASSWORD/environment-based
PRODUCTION_PASSWORD_ABSENT_BEHAVIOR=FAIL_CLOSED
CODE_REMEDIATION=COMPLETE
CREDENTIAL_ROTATION=COMPLETE
ROTATION_DATE=2026-09-13
VERIFICATION_METHOD=Supabase Session Pooler + read-only SELECT 1
ROTATED_DB_CREDENTIAL_VERIFICATION=PASS
DATABASE_CONNECTION=PASS
READ_ONLY_QUERY=PASS
SECRET_PRINTED=NO
REPOSITORY_REUSE_ASSESSMENT=NO_REUSE_FOUND_IN_REPOSITORY
```

The historical credential was rotated and its replacement successfully
verified using the method above. No password, token, API key, JWT, or
connection string is included in this record.

### Available log review and residual observation

The reviewed Supabase exports cover approximately 2026-09-06 through
2026-09-13. Logs covering the full period from the original 2026-06-07
repository exposure were not available in those exports. No evidence of
PostgreSQL password-authentication compromise was identified in the
available logs; this does not establish absence of compromise outside the
available evidence.

A short REST endpoint enumeration/probing burst occurred around 14:55 UTC
on 2026-09-12. Most guessed endpoints returned HTTP 404. One request to
`GET /rest/v1/users?select=*&limit=3` returned HTTP 206.

```
EVENT_DATE=2026-09-12
EVENT_TIME_APPROXIMATE=14:55 UTC
method=GET
pathname=/rest/v1/users
status=206
log_type=edge
user_agent=Mozilla/5.0
auth_user=null

ANOMALY_CLASSIFICATION=UNATTRIBUTED_REST_ENUMERATION_PROBING
POSTGRES_CREDENTIAL_COMPROMISE_EVIDENCE=NONE_IDENTIFIED_IN_AVAILABLE_LOGS
REST_EVENT_ATTRIBUTION=NOT_AVAILABLE
UNAUTHORIZED_DATA_DISCLOSURE=NOT_ESTABLISHED
ANOMALY_OUTCOME=REVIEWED_RESIDUAL_OBSERVATION
```

The retained/exported event lacks sufficient source-IP, JWT/API-key
identity, database-role, response-body, and historical-policy information
to attribute the request or determine whether unauthorized data disclosure
occurred. `auth_user=null` does not prove unauthenticated access. HTTP 206
alone does not establish request authorization or response contents.
The REST observation is not attributed to the historical PostgreSQL
credential. It is retained as a reviewed residual observation, not a finding
that no anomaly occurred.

### Residual risk and project-owner sign-off

```
FULL_HISTORICAL_LOG_REVIEW=NOT_POSSIBLE_FROM_AVAILABLE_EVIDENCE
AVAILABLE_LOG_WINDOW_REVIEWED=2026-09-06 through 2026-09-13
RESIDUAL_RISK=ACCEPTED_FOR_DEVELOPMENT_PROJECT_CLOSURE

SECURITY_REMEDIATION=COMPLETE
CREDENTIAL_ROTATION=COMPLETE
CODE_REMEDIATION=COMPLETE
REUSE_ASSESSMENT=COMPLETE
AVAILABLE_LOG_REVIEW=COMPLETE
ANOMALY_ASSESSMENT=COMPLETE_WITH_RECORDED_LIMITATION
REL_C1_STATUS=PASS_WITH_RECORDED_RESIDUAL_OBSERVATION
SIGNOFF_DATE=2026-09-13
PROJECT_OWNER=Srikanth
PROJECT_OWNER_SIGNOFF=RECORDED
INDEPENDENT_INFOSEC_SIGNOFF=NOT_CLAIMED
```

Srikanth accepts the recorded retention and attribution limitations for
closure of this development-project REL-C1 issue. This sign-off does not
claim independent corporate Security/InfoSec approval or prove that no
unauthorized disclosure occurred.

## Release exclusion boundary

Repository sanitization is complete. The following are untracked from the
release candidate (local copies preserved on disk; `HISTORY_REWRITE_PERFORMED=NO`):

- `data/CUR Jan 2026.xlsx` (provenance-unresolved sample workbook)
- `backup_unused/` (61 historical/archival paths)
- `backups/technology_tables_20260620_130633/` (generated historical export)
- `app.py.bak`
- `supabase/.temp/` (including the known historical REL-C1 credential-bearing
  `pooler-url` path; value never printed)
- `temp_uploads/`
- `test_env/data/uploaded_cur_file.xlsx` (confirmed not tracked)
- runtime databases, runtime logs, local caches
- `.venv/`, `.tmp/`
- local secrets
- known confidential real-client acceptance workbooks and customer/client
  evidence
- any other credential-bearing temporary artifact

No Git history was rewritten; these paths were removed from the current
tracked release state only (`git rm --cached`), and `.gitignore` was updated
to prevent recurrence.

## Project closure distinction

```
ENGINEERING_PROJECT_STATUS=CLOSED
COMMERCIAL_RELEASE_STATUS=READY_FOR_FINAL_RELEASE_STAGING
```

The engineering project is closed. REL-C1 is closed with the recorded
residual observation and project-owner development-project risk acceptance.
Repository sanitization is complete. The commercial release has not been
released, published, committed, pushed, or tagged. No release commit, push,
tag, or Git history rewrite is authorized here.
