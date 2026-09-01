# ACT-013 End-to-End Production Acceptance

## Status

`ACT-013 — PASS / END-TO-END PRODUCTION ACCEPTANCE`

`ACT-C13 — PASS / INTEGRATED PRODUCTION JOURNEY CERTIFIED`

The final manual browser journey and equivalent integrated automated acceptance
now cover the complete ACT-013 matrix. The browser journey retained one governed
CUR authority, entered the isolated Sample Enterprise, exercised Demo Home,
Services, Digital Twin, and Ask, and restored the exact CUR workspace without
re-upload or cross-context contamination.

## Current acceptance ledger

```text
ACT013-DEF-001   CLOSED
ACT013-DEF-002   CLOSED / mitigation verified
ACT013-DEF-003   CLOSED / fixed and manually verified
ACT013-DEF-004   CLOSED / durable reconstruction and execution verified
ACT013-DEF-004B  CLOSED / encrypted workspace resume manually verified
ACT013-DEF-005   CLOSED / safe source-selection return verified
ACT013-DEF-006   CLOSED / manual cross-context journey passed
ACT013-DEF-007   CLOSED / Demo Ask authority manually and automatically verified

ACT-013-M01      CEO Login / Home                         PASS
ACT-013-M02      Analyze Environment Render               PASS
ACT-013-M03      CUR Upload                               PASS
ACT-013-M04      Evidence Overview                        PASS
ACT-013-M05      Structural Discovery 184 / 10            PASS
ACT-013-M06      Legacy Parser Non-Blocking               PASS
ACT-013-M07      Financial Fail-Closed                    PASS
ACT-013-M08      Post-Admission Complete Render           PASS
ACT-013-M09      Confirm Mapping                          PASS
ACT-013-M10      Reject Mapping                           PASS
ACT-013-M11A     Executive Override Denial                PASS
ACT-013-M12      Governed COUNT Execution                 PASS

ACT-013-M13      Durable encrypted resume                  PASS — MANUAL
ACT-013-M14      Demo workspace journey                    PASS — MANUAL
ACT-013-M15      Demo supported / unsupported Ask          PASS — MANUAL
ACT-013-M16      Demo → Prospect exact restoration         PASS — MANUAL
ACT-013-M17      Services / Twin prospect fail-closed      PASS — MANUAL
ACT-013-A01      ACT-009 through ACT-013 regression        PASS — AUTOMATED
ACT-013-A02      Scope, tenant, and role isolation         PASS — AUTOMATED
ACT-013-A03      Restart, audit, purge, kill switch        PASS — AUTOMATED
ACT-013-A04      Safe failure and artifact controls        PASS — AUTOMATED

ACT-C13          PASS
```

## Final closure matrix

| Original acceptance requirement | Classification | Certification evidence |
| --- | --- | --- |
| Persona login, Home, Analyze Environment, and logout boundary | PASS — MANUAL | ACT-013 M01-M02 and the completed browser journey |
| CUR admission, overview, 184 records, 10 fields, and non-blocking legacy parser | PASS — MANUAL | ACT-013 M03-M08 |
| Confirm, Reject, trusted history, and unauthorized override denial | PASS — MANUAL | ACT-013 M09-M11A; durable authority was reconstructed after resume |
| Data-quality and governed capability behavior | PASS | Browser evidence plus ACT-009/ACT-013 integrated regression |
| COUNT returns 184 and Total Cost remains blocked without currency | PASS — MANUAL | ACT-013 M12 and restored CUR browser journey |
| Governed Ask record count, monetary blocking, ownership, and provenance | PASS | Manual CUR Ask journey plus ACT-008 integrated regression |
| Enterprise Context, reconciliation, canonical identity, graph, and dependencies | PASS — AUTOMATED | ACT-009 through ACT-013 integrated suites |
| Kill switch, trusted operations, audit correlation, restart, and readiness | PASS — AUTOMATED | ACT-011, ACT-011B, ACT-012, and ACT-013 restart suites |
| Durable encrypted resume without re-upload or latest-workspace inference | PASS — MANUAL | DEF-004B browser journey and owner/tenant-scoped automated tests |
| Prospect A/B scope and foreign-authority isolation | PASS — AUTOMATED | Prospect workspace and ACT-012 isolation/security suites |
| Demo ↔ Prospect presentation and Ask isolation | PASS — MANUAL | DEF-006/007 cross-context browser journey |
| Purge, tombstone retention, no revival, and other-scope integrity | PASS — AUTOMATED | ACT-011/012 persistence and adversarial suites |
| Safe failure presentation and sensitive-data suppression | PASS — AUTOMATED | ACT-012 security certification and production-route smoke tests |
| Production UI terminology, dead-end, and governance-message review | PASS | Manual journey plus executive-experience/workspace tests |

No acceptance item remains deferred. Earlier browser deferrals from ACT-005,
ACT-008, ACT-010, ACT-011, and ACT-012 were either exercised in the completed
ACT-013 browser journey or satisfied by equivalent integrated production,
restart, operations, and adversarial acceptance.

## Final cross-context evidence

- CUR Jan 2026 restored with 184 detail records, 10 fields, immutable governance,
  reconstructed normalization, executable COUNT, and safely blocked Total Cost.
- Sample Enterprise Home, Services, Digital Twin, and Ask used synthetic Demo
  authority. The supported attention question returned certified Demo decisions;
  an unsupported ownership question returned UNKNOWN.
- Returning to CUR restored the exact retained prospect authority. Ask used the
  prospect scope; Services and Digital Twin failed closed and displayed neither
  tenant nor synthetic services or graph evidence.
- Re-upload was not required and no governance authority was lost.

DEF-005 exposed that active/resumed workspaces bypassed the pre-analysis-only
"Choose another source" branch. The correction adds an explicit presentation-only
return from any active result to Step 1. It does not purge, delete, replace, or
log out the governed workspace. The retained analysis remains discoverable through
the owner- and tenant-scoped resume locator, and selecting a distinct source starts
a separate presentation journey without changing durable lifecycle authority.

DEF-006 exposed competing page-local context inference: Home recognized the demo
tenant while prospect-aware pages prioritized retained session objects. The shared
evidence-context boundary now carries an explicit active selection (`DEMO`,
`PROSPECT`, or `TENANT`), validates that selection against its backing authority,
and fails closed on forged or incomplete state. Demo launch explicitly selects the
isolated Sample Enterprise; exact governed resume explicitly selects its prospect
analysis. Switching presentation context does not delete, copy, merge, or replace
durable prospect evidence.

M12 manually verified that the resumed encrypted evidence retained governance,
normalization, capability authorization, and executable COUNT authority. The
production UI returned 184 from 184 records with zero invalid exclusions. Currency
authority remained absent and Total Cost remained blocked with
`REQUIRED_MEASURE_MISSING`; no monetary result was fabricated.

DEF-004 exposed production pilot services using process-local mapping and
normalization repositories while ACT-009 durability was configured only for
downstream production views. The correction must preserve mapping decisions,
history, normalization authority, and capabilities across logout, persona
transition, and runtime reconstruction. Logout and persona transition are not
purge operations.

DEF-004B adds an owner- and tenant-scoped durable workspace locator backed by
encrypted retained evidence. A clean session clearly offers an exact retained
analysis for resume without another browser upload. Multiple analyses require an
explicit selection; the route never infers "latest." Workspaces created before
this locator and encrypted-source retention existed cannot be reconstructed from
mapping decisions alone and require one controlled recreation after deployment.

## Acceptance configuration

Use a fresh shell and an isolated acceptance database. Secret values must be
supplied by the operator and must not be committed or printed.

```powershell
$env:ENVIRONMENT = "development"
$env:NEXORA_DEMO_MODE = "true"
$env:PUE_PILOT_DEV_MODE = "true"
$env:JWT_SECRET = "<process-only acceptance secret>"
$env:NEXORA_UNIVERSAL_EVIDENCE_DB = "<isolated acceptance database>"
$env:NEXORA_PROSPECT_DATA_KEY = "<Fernet key when encrypted prospect storage is used>"

.\.venv\Scripts\python.exe -m streamlit run app_main.py `
  --server.port 8522 --server.headless true
```

Only one process may listen on port 8522. Never use `cloud_advisor.db` as the
destructive acceptance database.

## Manual browser acceptance checklist

- [ ] Login as executive, operations/admin, and read-only personas; verify tenant
  and role, no Default Org or stale-session leakage, and logout clearing state.
- [ ] Open Home and Analyze Environment.
- [ ] Upload `CUR Jan 2026.xlsx`; verify successful Evidence Overview, filename,
  184 primary records, 10 fields, and no fatal legacy-parser outcome.
- [ ] Verify observed fields, candidate meaning, confidence/explanation, and
  confirmation-required state.
- [ ] As an authorized persona, exercise Confirm, Reject, and Override; verify
  rerun, effective state, history, and trusted actor. Verify read-only denial.
- [ ] Verify Data Quality distinguishes governed, valid, invalid, missing,
  unsupported, and blocked values.
- [ ] Verify Record Count is available and executes to 184.
- [ ] Verify Total Cost remains blocked for missing governed currency; no header
  USD, workbook total, or silent FX is used.
- [ ] Ask “How many records are in this evidence?” and verify 184.
- [ ] Ask “What is the total cost?” and “Assume USD and give me the total”; verify
  both monetary requests remain governed/blocked without an invented number.
- [ ] Verify Enterprise Context contains Checkout, Order Processing, i-test123,
  Alice, and CC-1001 with canonical identity, provenance, and relationships.
- [ ] Verify Source Reconciliation converges AWS and CMDB i-test123 evidence;
  ambiguous identity remains Needs Review and authorized Confirm/Reject works.
- [ ] Verify owner conflict remains explicit without silent selection.
- [ ] Verify Knowledge Graph and Dependency Analysis use the same canonical IDs.
- [ ] Ask “Who owns Checkout?” → Alice and “Which sources describe i-test123?” →
  AWS and CMDB. Verify foreign scope reveals nothing.
- [ ] Enable Kill Switch as operations/admin; verify execution and Ask block while
  evidence remains. Restart, verify enabled state, then disable it. Verify an
  unauthorized persona cannot change it.
- [ ] Restart Streamlit completely and verify evidence, mappings, normalization,
  capabilities, historical results, enterprise context, reconciliation, Ask, and
  audit reconstruct from durable state.
- [ ] Logout and return to Analyze Environment; select **Resume existing analysis**
  and verify the exact retained analysis reopens without another upload. Verify
  multiple analyses require explicit selection and foreign tenant/owner scopes are
  not listed.
- [ ] Switch Prospect A → B → A and verify no cross-scope presentation or cache
  contamination.
- [ ] Switch demo → prospect → demo and verify no cross-mode data or answer reuse.
- [ ] Verify the audit trace covers admission, mapping, normalization/capability,
  execution, materialization, reconciliation, and Ask with trusted actor and one
  correlation ID.
- [ ] Purge a disposable scope; verify audit retention, tombstones, other-scope
  integrity, and no revival through Ask/session/restart.
- [ ] Verify safe failure presentation has no traceback, path, SQL, or secret and
  includes an NX support reference where applicable.
- [ ] Confirm primary UI contains no ACT/PUE developer terminology, contradictory
  banners, dead ends, or unexplained governance blocks.

Record dated evidence and screenshots without committing client or sensitive data.
