# Nexora v1.1 acceptance remediation — 2026-09-15

Decision: **PASS / READY_FOR_REVIEW**, scoped to the three authorized integration defects and the existing administrator Ask correction. This is not a new end-to-end acceptance or release certification. The previous failed acceptance record remains unchanged.

Baseline: `feature/nexora-v1.1`, HEAD `3d7986bfc3641f6db37d54276db59f520db9498f`. All candidate changes remain uncommitted and unstaged. No branch switch, commit, push, tag, or merge was performed.

## Root causes and corrections

**A — local financial composition selected an empty repository.** LiveSourceService already published normalized AWS/Azure CLOUD_COST facts, but `_local_service` used `_EmptyTenantSpendRepository`. The local P1 service now uses a read-only SourceFact adapter. It reads current active facts with authenticated tenant scope and retains provider, account/subscription, service, period, currency, exact Decimal amount, source/execution identifiers, lineage and evidence references. Executive financial evidence and semantic financial retrieval use that same service. The reachable Cost Intelligence total-spend accessor now uses the canonical authenticated read model instead of an unscoped legacy mart/cache.

No second financial store was added. Production financial composition remains on its existing authority. Exact replay and corrected fact versions do not inflate totals. Overlapping cost periods, malformed amounts, mixed currencies, and requests requiring unsupported proration fail closed. Cloud observations do not establish complete enterprise coverage, business allocation, license cost, or SaaS cost. The existing service's explicit currency contract is retained; no conversion was added.

**B — the semantic catalogue advertised only enterprise search.** The existing Microsoft discovery service and Control Tower were not registered as semantic retrieval capabilities. The catalogue now includes cloud financial totals/breakdowns, Microsoft SKU/assignment/application evidence, source health and execution history. Handlers delegate to the existing financial, SaaS discovery and Control Tower authorities. The discovery service reads current active versions instead of historical rows and includes SourceFact/execution references and coverage state. No raw SQL access or question-string rules were added to Ask.

Missing usage and commercial pricing produce UNKNOWN without answer generation; assignment never becomes proof of usage. Incomplete discovery retains known evidence with PARTIAL coverage and an unknown count. Missing health remains UNKNOWN; known failed/stale sources remain retrievable. Tenant scope and existing role authorization are checked before authority retrieval. Synthetic tests exercise multiple question phrasings through the provider-neutral plan validator/executor and real copilot composition. The synthetic planner supplies explicit plans: these tests certify capability routing and grounding, not live model natural-language accuracy.

**C — the audit hard-coded a historical blocked decision.** `build_inventory()` and `build_manifest()` in `scripts/audit_database_bootstrap.py` returned BLOCKED and stale missing-DDL/tooling explanations independently of the current chain. Historical references remain in `docs/cmp/CMP-P6-DEF-001`, `docs/cmp/CMP-P6-SC-002/REPORT.md`, and the subsequent RC-001 closure in `docs/cmp/CMP-P6-RC-001/REPORT.md`. The current bootstrap already defines the seven public prerequisites, including canonical v1 approvals; the existing dated and Data Fabric migrations provide the current financial/SourceFact authorities.

The audit now evaluates ordered qualified-definition dependencies, required authority definitions, migration continuity/completeness, and local initializer presence. Its manifest includes public bootstrap, 17 dated migrations, 23 Data Fabric migrations, the Universal Evidence SQLite lifecycle, the SQLite SourceFact prerequisite and both WS2/WS3 connector migrations. It inventories the current candidate's nonignored Python/SQL files, including untracked source, so staging is not necessary for reproducibility. Required-migration and prerequisite-removal tests retain BLOCKED behavior. Both generated JSON files reproduce exactly. No historical migration changed.

`READY_FOR_REPLAY` is a static contract result, not proof of PostgreSQL execution. The lexical audit does not validate PostgreSQL syntax, every column/type dependency, dynamic SQL or all optional legacy callers. It retains unresolved legacy call candidates for review; they are not an execution allowlist. Deployment still requires the stated Supabase auth prerequisites and an empty application schema. The prior isolated initdb restricted-token failure remains an environment limitation; no PostgreSQL replay was attempted in this remediation.

**Existing administrator correction retained.** The preexisting `enterprise_copilot/composition.py` change makes scenario composition optional for roles outside ScenarioService's narrower existing read policy. `client_admin` can initialize authorized Ask reads without gaining scenario rights; `super_admin` retains scenario access. The preexisting boundary tests also preserve logout clearing of tenant/role state.

## Verification

- Synthetic AWS USD 100.25 and Azure USD 49.75 were authenticated/extracted through test provider substitutes, then passed through the real adapters, normalization, source lifecycle, SourceFact publication, persistence and financial service. SourceFact total = P1 total = executive cloud value = USD 150. Provider and service breakdowns reconcile exactly; tenant B sees no tenant A facts. A corrected AWS observation produces USD 170 without replay inflation.
- The same synthetic tenant has two Microsoft SKUs, one user assigned both, and a registered application with unknown publisher. SKU filtering yields one E5-assigned user; multiple-license and application queries return persisted evidence. Failure, stale-source, unknown pricing/usage, unavailable discovery, unauthorized role and forged-tenant cases are covered.
- An XLSX upload under the same authenticated tenant passes existing admission, semantic confirmation and normalization. Its independent observation does not inflate connector cloud spend. Existing uploaded-evidence authority boundaries are preserved.
- The six affected domains pass their bounded automated contracts: technology discovery, license intelligence, financial intelligence, Ask, executive financial handoff and database bootstrap. This does not replace the pending integrated browser/live-provider acceptance.
- Combined focused run: **235 passed**, 5 existing warnings, 57.10 seconds. Breakdown: connectors 57; remediation/admin boundaries 18; Ask/planner 24; security 50 (including 13 bootstrap tests); financial 86.
- Full regression: **2,002 passed, 7 skipped, 1 known failure**, 12 warnings, 194.21 seconds. The only failure is `tests/test_persona_authentication.py::test_all_canonical_personas_seed_and_authenticate`: the documented demo/local organization-ID mismatch. New regressions: **0**. External Supabase integration was explicitly disabled with `P3_SUPABASE_RUN_INTEGRATION=0`.
- After the full run, the remediation test helper was strengthened to call the real `enterprise_ai_copilot` composition instead of assembling the orchestrator with mock search/intelligence. All **18 remediation/admin tests passed again**, in 32.00 seconds. Product code did not change after the full regression run.
- Ruff: PASS for all 13 changed/untracked candidate Python files. `git diff --check`: PASS.

Evidence logs and JUnit results are in ignored `.tmp/v11-remediation-focused.{log,xml}`, `.tmp/v11-remediation-full.{log,xml}`, and `.tmp/v11-remediation-composition.{log,xml}`. Tests used isolated `.tmp` basetemps and synthetic data. No live AWS, Azure, Microsoft or AI-provider acceptance was performed. No credentials or customer file contents are included in this report.

## Requested result

```text
NEXORA_V1_1_ACCEPTANCE_REMEDIATION=PASS
REMEDIATION_STATUS=READY_FOR_REVIEW
PREEXISTING_ACCEPTANCE_FIX_FILES=enterprise_copilot/composition.py; tests/release/test_v11_acceptance_boundaries.py
PREEXISTING_ACCEPTANCE_FIX_CLASSIFICATION=BOUNDED_ASK_INITIALIZATION_AND_AUTH_BOUNDARY_TESTS
DEFECT_A_ROOT_CAUSE=Local financial composition selected an empty repository instead of persisted cloud SourceFacts
DEFECT_A_FIXED=YES
CLOUD_SOURCEFACT_FINANCIAL_BRIDGE=PASS
AWS_FINANCIAL_RECONCILIATION=PASS
AZURE_FINANCIAL_RECONCILIATION=PASS
EXECUTIVE_FINANCIAL_HANDOFF=PASS
DEFECT_B_ROOT_CAUSE=Existing discovery and source authorities were absent from the semantic capability catalogue
DEFECT_B_FIXED=YES
M365_ASK_CAPABILITY=PASS
LICENSE_ASK_CAPABILITY=PASS
SOURCE_HEALTH_ASK_CAPABILITY=PASS
SOURCE_EXECUTION_ASK_CAPABILITY=PASS
SEMANTIC_VARIATION=PASS (synthetic provider-neutral routing/grounding contract)
ADMIN_ASK_INITIALIZATION_FIX=PASS
AUTHORIZATION_WEAKENED=NO
DEFECT_C_ROOT_CAUSE=Historical BLOCKED status was hard-coded; current dependencies and connector migrations were not evaluated
DEFECT_C_FIXED=YES
DATABASE_DEPLOYMENT_STATUS=READY_FOR_REPLAY (static contract only)
DATABASE_BOOTSTRAP_AUDIT=PASS
MIGRATION_MANIFEST_CONSISTENT=YES
SCHEMA_INVENTORY_CONSISTENT=YES
POSTGRES_REPLAY=DEFERRED_ENVIRONMENT
TECHNOLOGY_INTELLIGENCE=PASS
LICENSE_INTELLIGENCE=PASS
FINANCIAL_INTELLIGENCE=PASS
ASK_NEXORA=PASS
EXECUTIVE_EXPERIENCE=PASS
TENANT_ISOLATION=PASS
AUTHORIZATION=PASS
SECRET_LEAKAGE=NO
FOCUSED_TEST_RESULT=235 passed; final real-composition remediation rerun 18 passed
SECURITY_TEST_RESULT=50 passed
ASK_TEST_RESULT=24 passed plus real-composition remediation cases
FINANCIAL_TEST_RESULT=86 passed plus exact synthetic connector reconciliation
DATABASE_TEST_RESULT=13 passed
FULL_REGRESSION_RESULT=2002 passed, 7 skipped, 1 documented preexisting failure
NEW_REGRESSIONS=0
RUFF=PASS
DIFF_CHECK=PASS
CODE_CHANGES_REQUIRED=YES (implemented; no further remediation changes identified)
COMMIT_CREATED=NO
PUSH_PERFORMED=NO
TAG_CREATED=NO
MERGE_PERFORMED=NO
V1_CLOSURE_RECORD_TRACKED=NO
V1_CLOSURE_RECORD_STAGED=NO
READY_FOR_ACCEPTANCE_RERUN=YES
```

## Exact working-tree file inventory

Modified tracked files:

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

Untracked candidate files (not staged):

```text
docs/release/NEXORA_V1_1_ACCEPTANCE_REMEDIATION.md
repositories/source_fact_financial_repository.py
services/governed_source_capabilities.py
tests/release/test_v11_acceptance_boundaries.py
tests/release/test_v11_authority_bridges.py
```

Preexisting untracked evidence preserved without edits (not staged):

```text
docs/release/NEXORA_V1_1_END_TO_END_ACCEPTANCE.md
docs/release/NEXORA_V1_PROJECT_CLOSURE.md
```

The v1 closure record still has SHA-256 `6696F9883C3711C6B3FA933957E61A69C29ED76541EAD002825605BCF19BEC94`. Next permitted checkpoint is review of this uncommitted candidate, followed by separately authorized acceptance rerun. Neither acceptance rerun nor release certification was performed here.
