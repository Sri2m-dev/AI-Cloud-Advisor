# Nexora v1.1 End-to-End Commercial Acceptance Rerun ? 2026-09-16

Decision: **PASS / PASS**, with the explicit external/environment deferrals below. This checkpoint evaluates the current uncommitted candidate; it is not release certification.

## Candidate and acceptance boundary

Branch: `feature/nexora-v1.1`. HEAD: `3d7986bfc3641f6db37d54276db59f520db9498f`, matching the requested baseline. WS1?WS4 remain frozen. The remediation and its tests were preserved byte-for-byte; no product code, historical migration, or repository test was changed during this rerun. The bootstrap command regenerated identical JSON artifacts. Only this report is intentionally updated; probes/logs are under ignored `.tmp/`.

The preceding acceptance on 2026-09-15 was **FAIL / DEFECT_TO_FIX**: cloud SourceFacts did not reach local financial composition; Microsoft discovery was absent from customer-facing semantic retrieval; the bootstrap audit reported BLOCKED. Administrator Ask initialization had received a bounded correction. This rerun supersedes that decision only within the same synthetic/local acceptance boundary. It does not claim live provider, hosted database, or live AI-model certification.

## Integrated commercial journey

A fresh synthetic organization and initial administrator were created through onboarding services, followed by invitation acceptance, password login, authenticated tenant binding, and a verified clean workspace. The harness redirects the database connection to a disposable file; customer setup uses application services, with no developer seed or direct SQL setup. Onboarding/authorization tests also cover invitation expiry, revocation, duplicate invitations, foreign-tenant access, production demo-seeding exclusion, and fail-closed context.

AWS, Azure, and Microsoft 365 were independently registered, validated, activated, and synced through real adapters, normalization, lifecycle, and SourceFact persistence. Only provider authentication/extraction were synthetic substitutes. Six facts were persisted: two cloud costs, a Microsoft user identity, an application/service principal, a subscribed SKU, and a license assignment. Restart preserved all sources, executions, and facts. Existing focused connector tests independently exercise provider contracts, safe failures, encryption, redaction, scheduling, and tenant restrictions.

For the same customer and scope, **SOURCEFACT_COST_TOTAL = FINANCIAL_AUTHORITY_TOTAL = EXECUTIVE_CLOUD_TOTAL = ASK_CLOUD_TOTAL = USD 150** (AWS USD 100 + Azure USD 50). Provider/service breakdowns reconcile. Evidence retains provider, account/subscription, service, period, currency, source, execution identity, lineage, and provenance; authenticated tenant scope is retained. The separate real-composition regression also reconciles AWS 100.25 + Azure 49.75 and tests corrected versions, replay deduplication, mixed currencies, and overlapping/partial periods.

The production-page composition chain was inspected: shared executive workspace ? EnterpriseIntelligenceQueryService ? canonical P1 financial service. The rerun called that composition for Command Center, Executive Brief, and Investment & Value: each exposes `$150` cloud spend with authority `P1:pvt-003c1-v1`. No dashboard/provider bypass or second cost store was introduced. Production financial composition remains the preexisting authority; this synthetic local test does not prove hosted connector-to-financial deployment.

Microsoft SKU, assigned-user, and application records are available through registered governed semantic capabilities. User identity ingestion is covered separately; this does not claim a new general directory-user search capability. Missing publisher and commercial cost remain UNKNOWN. Assignment never establishes active usage: semantic assignment evidence carries `actively_used=None` and `utilization=UNKNOWN`. Explicit usage and cost requests return UNKNOWN without synthesis. Technology/license acceptance covers governed discovery through Ask, not an additional enterprise-registry materialization.

Same-tenant XLSX admission, semantic confirmation, and governed normalization pass the real-composition test without inflating connector cloud spend. Full regression covers the broader upload/document, Universal Evidence, Data Fabric, persistence, and normalization contracts.

## Ask, executive, and security evidence

The combined probe executed **24 phrasings**, two each for cloud total, provider spend, service spend, discovered Microsoft applications, subscribed SKUs, assignments, unavailable usage, unavailable cost, source health, execution history, optimization opportunity, and enterprise technology context. Each uses an explicit synthetic provider-neutral plan through the real registered planner validator/executor and copilot composition. No keyword/regex/FAQ routing was added. This proves routing/grounding contracts, not a live model's ability to choose a plan from natural language.

Available evidence produces provenance citations. Unsupported region constraints are rejected. Foreign-tenant financial Ask returns UNKNOWN with no citations. A newly synced source without a freshness schedule remains UNKNOWN, rather than falsely healthy; failed/stale retrieval is covered by the focused bridge tests. Missing optimization/dependency evidence returns unsupported/unknown without invented savings or relationships using the existing mock generator. For those search-only cases, answer wording is provider-dependent; live-model synthesis was not evaluated.

Administrator Ask initializes with the existing authorized read capabilities. Client administrators do not gain ScenarioService privileges; super administrators retain existing access. Focused tests verify denial before semantic planning/retrieval and real Streamlit logout clearing identity, role, tenant, authorization list, and prior prospect context. Security/connector tests pass tenant isolation, role checks, encrypted credentials, no secret redisplay/logging, and fail-closed production contracts.

Existing executive, financial decision, optimization, approval, and navigation suites pass. Their scope includes Home/customer journey, role-gated workspaces, canonical decisions/approvals, distinct potential/approved/realized investment values, and Data Source Control Tower integration. No unsupported SaaS/license price, realized savings, enterprise coverage, or currency conversion is inferred.

## Database, recovery, and external deferrals

Executed `.venv/Scripts/python.exe scripts/audit_database_bootstrap.py --output-dir docs/cmp/CMP-P6-DEF-001`. Result: **READY_FOR_REPLAY**, executable static contract, no blockers. Both artifacts match their entering hashes. Manifest includes `migrations/connectors/0001_live_source_control.sql` and `0002_add_m365_provider.sql`. No historical migration changed. This is a static dependency/completeness audit, not PostgreSQL execution proof.

SQLite backup/restore reopened the synthetic customer state through LiveSourceRepository: one organization, three sources, three executions, and six SourceFacts. A supplemental restore again retained six facts.

| Deferred gate | Status | Evidence / limitation |
|---|---|---|
| Live AWS | DEFERRED_EXTERNAL_ENVIRONMENT | Synthetic provider evidence only; no customer AWS account used |
| Live Azure | DEFERRED_EXTERNAL_ENVIRONMENT | Synthetic provider evidence only; no customer subscription used |
| Live Microsoft | DEFERRED_EXTERNAL_ENVIRONMENT | Synthetic discovery only; no customer tenant used |
| PostgreSQL replay | DEFERRED_ENVIRONMENT | Isolated initdb failed before server startup: restricted-token errors 87/3 |
| PostgreSQL backup/restore | DEFERRED_ENVIRONMENT | Same local initialization failure; SQLite recovery passed |
| Browser acceptance | DEFERRED_ENVIRONMENT | Browser initialization failed before opening a page: missing sandboxPolicy metadata |

Prior browser UAT is retained as historical supporting evidence. Fresh browser validation of remediation-affected Ask/financial flows remains explicitly deferred; service and Streamlit tests are not represented as fresh integrated browser UAT. External database integration was disabled with `P3_SUPABASE_RUN_INTEGRATION=0`. No live AI-provider call was made.

## Verification and reproduction

Focused acceptance: **295 passed**, 11 warnings, 96.67 seconds. Counts: auth 24; security 50; connectors 57; release/bridges/admin boundaries 28; executive experience 31; financial decisions 31; P1 22; P2 18; approval/read-model services 4; integrated/normalization evidence 6; semantic planner/copilot 24. Includes all 18 remediation/admin boundary tests. Warnings include existing deprecations and sandbox denial of the default pytest cache; full regression uses an isolated cache.

Full regression: **2,003 passed, 7 skipped, 0 failed**, 12 warnings, 219.38 seconds. The formerly documented `tests/test_persona_authentication.py::test_all_canonical_personas_seed_and_authenticate` passed in this run (verified in JUnit). Therefore zero known failures were observed; no product change was made to address that historical mismatch. Total collected remains 2,010, matching remediation. New regressions: **0**.

Ruff: **PASS**, all 13 modified/untracked candidate Python files. Diff check: **PASS**, including final report whitespace validation. No tracked runtime database, log, private-key, or `.env` paths were found. Closure evidence remains untracked and unchanged (SHA-256 `6696f9883c3711c6b3fa933957e61a69c29ed76541ead002825605bcf19bec94`). No files staged.

Commands (PowerShell; repository virtual environment uses Python 3.11.9):

```powershell
$env:P3_SUPABASE_RUN_INTEGRATION='0'
.venv/Scripts/python.exe -m pytest tests/auth tests/security tests/connectors tests/release tests/executive_experience tests/financial_decision_product tests/cmp_p1 tests/cmp_p2 tests/services/test_v1_approval_authority.py tests/services/test_financial_read_models.py tests/universal_evidence/test_act013_integrated_acceptance.py tests/universal_evidence/test_pue_governed_normalization_pilot.py tests/enterprise_registry/test_semantic_planner.py tests/enterprise_registry/test_enterprise_ai_copilot.py -q --basetemp=.tmp/v11-rerun-focused-temp --junitxml=.tmp/v11-rerun-focused.xml
.venv/Scripts/python.exe -m pytest -q -o cache_dir=.tmp/v11-rerun-pytest-cache --basetemp=.tmp/v11-rerun-full-temp --junitxml=.tmp/v11-rerun-full.xml
.venv/Scripts/python.exe .tmp/v11_rerun_supplement.py
.venv/Scripts/python.exe .tmp/v11_rerun_recovery_probe.py
.venv/Scripts/python.exe scripts/audit_database_bootstrap.py --output-dir docs/cmp/CMP-P6-DEF-001
git diff --check
```

Evidence: `.tmp/v11-rerun-focused.{log,xml}`, `.tmp/v11-rerun-full.{log,xml}`, `.tmp/v11-rerun-commercial-probe.{log,json}`, `.tmp/v11-rerun-supplement.{log,json}`, `.tmp/v11-rerun-recovery-report.json`, `.tmp/v11-rerun-ruff.log`, and `.tmp/v11-rerun-candidate.json`. Probes contain synthetic data only. The initial default Python lacked pytest; execution was switched to the existing virtual environment. Probe-only assumptions about unscheduled source health, mock answer formatting, and valid UUIDs were corrected; no product remediation was required.

## Entering working-tree record

### `git status --short`

```text
 M docs/cmp/CMP-P6-DEF-001/migration_manifest.json
 M docs/cmp/CMP-P6-DEF-001/schema_inventory.json
 M enterprise_copilot/composition.py
 M enterprise_copilot/orchestrator.py
 M repositories/cost_intelligence_repository.py
 M scripts/audit_database_bootstrap.py
 M services/enterprise_spend_composition.py
 M services/enterprise_spend_service.py
 M services/financial_read_models.py
 M services/saas_discovery_intelligence_service.py
 M tests/security/test_database_bootstrap_audit.py
?? docs/release/NEXORA_V1_1_ACCEPTANCE_REMEDIATION.md
?? docs/release/NEXORA_V1_1_END_TO_END_ACCEPTANCE.md
?? docs/release/NEXORA_V1_PROJECT_CLOSURE.md
?? repositories/source_fact_financial_repository.py
?? services/governed_source_capabilities.py
?? tests/release/test_v11_acceptance_boundaries.py
?? tests/release/test_v11_authority_bridges.py
```

### `git diff --stat`

```text
 docs/cmp/CMP-P6-DEF-001/migration_manifest.json |  53 ++-
 docs/cmp/CMP-P6-DEF-001/schema_inventory.json   |  58 ++-
 enterprise_copilot/composition.py               |  15 +-
 enterprise_copilot/orchestrator.py              |  80 +++-
 repositories/cost_intelligence_repository.py    |  25 +-
 scripts/audit_database_bootstrap.py             | 464 ++++++++++++++++++------
 services/enterprise_spend_composition.py        |   3 +-
 services/enterprise_spend_service.py            |   5 +
 services/financial_read_models.py               |  14 +-
 services/saas_discovery_intelligence_service.py | 229 ++++++------
 tests/security/test_database_bootstrap_audit.py | 140 ++++---
 11 files changed, 754 insertions(+), 332 deletions(-)
```

### `git diff --name-only`

```text
docs/cmp/CMP-P6-DEF-001/migration_manifest.json
docs/cmp/CMP-P6-DEF-001/schema_inventory.json
enterprise_copilot/composition.py
enterprise_copilot/orchestrator.py
repositories/cost_intelligence_repository.py
scripts/audit_database_bootstrap.py
services/enterprise_spend_composition.py
services/enterprise_spend_service.py
services/financial_read_models.py
services/saas_discovery_intelligence_service.py
tests/security/test_database_bootstrap_audit.py
```

### `git rev-parse --abbrev-ref HEAD`

```text
feature/nexora-v1.1
```

### `git rev-parse HEAD`

```text
3d7986bfc3641f6db37d54276db59f520db9498f
```

## Final acceptance result

PASS values are scoped to the automated/synthetic contracts described above. No product acceptance defect remains in this rerun. Only the explicitly allowed external/environment gates are deferred.

```text
NEXORA_V1_1_END_TO_END_ACCEPTANCE_RERUN=PASS
ACCEPTANCE_STATUS=PASS
CUSTOMER_ONBOARDING=PASS
CUSTOMER_REQUIRES_DEVELOPER_SEEDING=NO
CUSTOMER_REQUIRES_DIRECT_DATABASE_SETUP=NO
TENANT_ISOLATION=PASS
AWS_INGESTION=PASS
AZURE_INGESTION=PASS
M365_INGESTION=PASS
UPLOAD_INGESTION=PASS
LIVE_AWS_ACCEPTANCE=DEFERRED_EXTERNAL_ENVIRONMENT
LIVE_AZURE_ACCEPTANCE=DEFERRED_EXTERNAL_ENVIRONMENT
LIVE_MICROSOFT_ACCEPTANCE=DEFERRED_EXTERNAL_ENVIRONMENT
UNIVERSAL_EVIDENCE=PASS
DATA_FABRIC=PASS
TECHNOLOGY_INTELLIGENCE=PASS
LICENSE_INTELLIGENCE=PASS
FINANCIAL_INTELLIGENCE=PASS
OPTIMIZATION_INTELLIGENCE=PASS
ASK_NEXORA=PASS
ADMINISTRATOR_ASK_INITIALIZATION=PASS
PRIVILEGE_EXPANSION=NO
EXECUTIVE_EXPERIENCE=PASS
DECISIONS_APPROVALS=PASS
INVESTMENT_VALUE=PASS
DATA_SOURCE_CONTROL_TOWER=PASS
PERSISTENCE=PASS
FAILURE_BEHAVIOR=PASS
LOGOUT_SESSION_ISOLATION=PASS
SECURITY=PASS
DATABASE_BOOTSTRAP=PASS
BOOTSTRAP_STATUS=READY_FOR_REPLAY
POSTGRESQL_REPLAY=DEFERRED_ENVIRONMENT
BACKUP_RESTORE=PASS (SQLite); DEFERRED_ENVIRONMENT (PostgreSQL)
BROWSER_ACCEPTANCE=DEFERRED_ENVIRONMENT
FOCUSED_ACCEPTANCE_TESTS=295 passed
FULL_REGRESSION_RESULT=2003 passed, 7 skipped, 0 failed
NEW_REGRESSIONS=0
KNOWN_NON_BLOCKING_FAILURES=0 observed; prior persona mismatch did not reproduce
RUFF=PASS
DIFF_CHECK=PASS
RELEASE_BOUNDARY=PASS
CODE_CHANGES_REQUIRED=NO
COMMIT_CREATED=NO
PUSH_PERFORMED=NO
TAG_CREATED=NO
MERGE_PERFORMED=NO
READY_FOR_V1_1_RELEASE_CERTIFICATION=YES
```

Stop condition reached. Return this report to the project owner for approval. No release certification, commit, push, tag, merge, or new workstream was started.
