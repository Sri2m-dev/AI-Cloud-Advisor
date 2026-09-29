# CLR-001B / CLR-001C local closure certification

Date: 2026-09-29

BRANCH=program/nexora-production-activation
HEAD_BEFORE=a8bb40d25a8d09561cba896fb1fdb089b2f3e2ae
CLR-001B=CLOSED
CLR-001C=CLOSED (local application-runtime UAT)

The complete certified package now uses the existing admission, semantic governance,
normalization, SourceFact publication, reconciliation, coverage and intelligence services.
Analyze Environment renders all four sources together. Missing billing months are derived
from the declared inclusive calendar period for each account observed in billing evidence.
An organization account alone does not establish a billing obligation. No sample account,
month, package identifier or expected findings drive product behavior.

The package route fails closed instead of falling back to cost-only analysis. Existing
single-file CSV/XLSX processing is preserved. SourceFact storage is separated by authenticated
organization, tenant, prospect and manifest identity, under the prospect retention directory.
Retained package results cannot be replayed across owner, organization or prospect boundaries.
Workspace context and reset behavior include package evidence. Existing governance override
permissions remain authoritative; no elevated user role is manufactured.

PACKAGE_VALIDATION=PASS
ENCRYPTED_PERSISTENCE=PASS
FOUR_SOURCE_ADMISSION=PASS
SEMANTIC_GOVERNANCE=PASS
NORMALIZATION=PASS
SOURCEFACTS=PASS
RECONCILIATION=PASS
GOVERNED_COVERAGE=PASS
CROSS_SOURCE_INTELLIGENCE=PASS
ORACLE_ACCEPTANCE=9/9; 0 MISMATCH; 0 MISSING
ANALYZE_ENVIRONMENT_PACKAGE_ROUTE=PASS
LEGACY_SINGLE_FILE_REGRESSION=PASS
SECURITY_TENANT_ISOLATION=PASS
APPLICATION_UAT=PASS (Streamlit AppTest actual upload, render and rerun)
TEST_TOTAL=861
TEST_FAILURES=0
NEW_REGRESSIONS=0

## Physical package evidence

The actual supplied EVD-SAMPLE-7 directory was uploaded through the real Analyze Environment
form using Streamlit AppTest, not a replacement UI or mocked package service.

| Measure | Actual |
| --- | --- |
| Organization rows | 4 |
| Inventory rows | 31 |
| Cost rows | 5,220 |
| Application mapping rows | 7 |
| Normalization runs | 23 |
| Normalized records | 42,075 |
| Current SourceFacts | 15,809 |
| Reconciliation proposals | 3 |
| Governed/evidenced concepts | 13/13 |
| Partial/blocked concepts | 0/0 |
| Supported/blocked capabilities | 8/6 |
| Evidence-derived cost | 94257.100233 USD |

The package identity, four-source table, concept coverage, findings and provenance rendered
without application exceptions. Unsupported capabilities remained blocked. Encrypted source
roundtrip matched all four original source files byte-for-byte. Mapping decision IDs,
normalization references and finding evidence references were retained.

Actual output was frozen before the acceptance runner opened the external oracle.
Product runtime never reads the oracle; JSON cannot be declared as an analytical source.

FROZEN_ACTUAL_SHA256=bc51f11c53212e37982fee84a4e35485e6257dd12c9b5a840ac92c5676c31c28

Local evidence (ignored, not committed):
- `.tmp/clr-certified-release/actual-frozen.json`
- `.tmp/clr-certified-release/acceptance.json`
- `.tmp/clr-final-regression-04.log`
- `.tmp/clr-scope-checks.json`

| Oracle category | Result |
| --- | --- |
| untagged_resources | MATCH |
| inventory_without_cost | MATCH |
| cost_without_inventory | MATCH |
| cost_account_not_in_org | MATCH |
| suspended_account_in_org | MATCH |
| app_mapping_unknown_account | MATCH |
| missing_cost_month | MATCH |
| sanitisation_flags | MATCH |
| pii_notice | MATCH |

## Validation and reproducibility

```powershell
.venv\Scripts\python.exe -m pytest tests/universal_evidence tests/prospect_intake tests/executive_experience/test_customer_journey_ux.py tests/cmp_p4/test_source_fact_authority.py tests/security/test_report_tenant_isolation.py -q --basetemp .tmp/clr-final-regression-04 -p no:cacheprovider
.venv\Scripts\python.exe -m tests.universal_evidence.certify_evidence_package_acceptance --package <physical-package-directory> --oracle <external-oracle-json> --output <new-local-output-directory>
```

Use a fresh basetemp directory for reruns. The final regression run passed 861 tests in
38.34 seconds. Five existing third-party SWIG deprecation warnings remain. The suite includes
all package tests, semantic governance, normalization, runtime, coverage, application route,
prospect isolation, affected security and legacy upload checks. Expired-clock and obsolete
JSON-exclusion test assertions were corrected without weakening their remaining checks.
The legacy AppTest omits page-link navigation because it runs a single page without the
application navigation registry; the upload, legacy spend and governed admission are checked.

Changed Python files pass py_compile and Ruff. Git diff whitespace checks pass. Scoped
secret-pattern, debug/TODO and product sample-hardcoding scans found no matches.

## Application runtime and limitations

The supported `python -m streamlit run app_main.py` runtime launched locally at
127.0.0.1:8531 and its health endpoint returned `ok`.
Browser automation bootstrap failed before accessing a page with:
`Mcp error: -32602: js: codex/sandbox-state-meta: missing field sandboxPolicy`.
Consequently this certifies application-runtime UAT, not browser visual layout or live browser
navigation. No browser pass is claimed. The user's authorized fallback was exercised using
the actual Streamlit upload widget, processing route, rendered elements and rerun behavior.

Remaining environment items: repair browser-tool configuration for optional visual verification;
configure deployment-managed encryption keys and durable runtime paths when deploying.
External deployment, live cloud certification and CLR-002 were not performed. No new cross-page
Ask capability is claimed; unsupported information remains unknown/blocked.

MAIN_SHA=f457f8afac89a1c196e9992a99e7b8b652182c7a
V1_1_0_SHA=f457f8afac89a1c196e9992a99e7b8b652182c7a (peeled commit)
V1_1_0_TAG_OBJECT=a796453dd46d42d900309c5ce970f88dc0744059
IMMUTABILITY=PASS
PUSH=NONE

## Exact commit scope

- `docs/acceptance/CLR_001B_001C_CLOSURE.md`
- `pages/analyze_environment.py`
- `shared/evidence_context.py`
- `tests/executive_experience/test_customer_journey_ux.py`
- `tests/universal_evidence/certify_evidence_package_acceptance.py`
- `tests/universal_evidence/test_act010_production_workflow.py`
- `tests/universal_evidence/test_evidence_package.py`
- `tests/universal_evidence/test_evidence_package_application.py`
- `tests/universal_evidence/test_evidence_package_composition.py`
- `tests/universal_evidence/test_evidence_package_coverage.py`
- `tests/universal_evidence/test_evidence_package_governance.py`
- `tests/universal_evidence/test_evidence_package_intelligence.py`
- `tests/universal_evidence/test_evidence_package_normalization.py`
- `tests/universal_evidence/test_evidence_package_persistence.py`
- `tests/universal_evidence/test_evidence_package_route.py`
- `tests/universal_evidence/test_evidence_package_runtime.py`
- `tests/universal_evidence/test_evidence_package_semantics.py`
- `tests/universal_evidence/test_pue011_product_closure.py`
- `universal_evidence/pilot/admission.py`
- `universal_evidence/pilot/evidence_package.py`
- `universal_evidence/pilot/evidence_package_composition.py`
- `universal_evidence/pilot/evidence_package_coverage.py`
- `universal_evidence/pilot/evidence_package_governance.py`
- `universal_evidence/pilot/evidence_package_intelligence.py`
- `universal_evidence/pilot/evidence_package_persistence.py`
- `universal_evidence/pilot/evidence_package_runtime.py`
- `universal_evidence/pilot/evidence_package_semantics.py`
