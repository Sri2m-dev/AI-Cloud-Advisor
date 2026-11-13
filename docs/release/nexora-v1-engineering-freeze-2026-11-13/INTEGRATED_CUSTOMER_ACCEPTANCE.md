# NEXORA V1 Integrated Customer Acceptance

Execution date: 2026-11-13
Data: disposable synthetic Customer A and Customer B identities and evidence.

## Environment boundary

The full browser journey ran against one isolated route-freeze deployment:
Compose project `nexora-v1-route-freeze-20261113-r1`, Streamlit at
`127.0.0.1:18517`, its isolated identity services, and its PostgreSQL
customer-workflow database. The application container was restarted without
recreating the database. Protected Docker projects and cloud/Supabase resources
were not used or modified.

All journey steps below used this same application, authentication path, and
database. API-only regression tests and their results are reported separately
in [Security and Regression Results](./SECURITY_AND_REGRESSION_RESULTS.md).

## Journey evidence

| Step | Result |
|---|---|
| Customer A login | **PASS.** Authenticated as a synthetic executive in Synthetic Customer A. |
| Create/resume tenant workspace | **PASS.** The workspace `Synthetic Customer A - Route Freeze 2026-11-13` was available after login and after reauthentication. |
| Upload and validate synthetic evidence | **PASS.** `route-freeze-synthetic-costs.csv` was validated and persisted. The evidence record was `fd429df7-21c2-45d9-955f-f2254784accd`; its displayed SHA-256 was `48d0a049f3fd4476486962f97e1e2849f53ec7580cf19567f935616d05f327a3`. |
| Bounded Ask | **PASS.** Asked “How many evidence records are present?” The grounded response reported two evidence rows and linked to the saved evidence record. |
| Customer decision | **PASS.** The decision “Review the uploaded cost evidence through staged approval” was persisted against the grounded workflow. |
| Finance → CIO → CEO approvals | **PASS.** Three distinct authorized synthetic users completed the sequence. The final state was `APPROVED`; the append-only history retained all three roles and reasons. |
| Evidence-linked export | **PASS for generation and persistence.** Export `2e7b1580-7226-5518-8021-dd762dfa0915` was created for approval request `7903c3b5-0063-59f7-b519-4af2171ba775`. The package and evidence/approval links were validated through the same live PostgreSQL-backed service. |
| Logout and reauthentication | **PASS.** Customer A logged out and reauthenticated; the existing workspace, evidence, Ask result, decision, approval history, and export remained available. |
| Application restart | **PASS.** Only the application container was restarted. Its health endpoint returned HTTP 200 after restart, and the authenticated workflow remained available. This proves application-restart persistence; the database service itself was not restarted during this browser journey. |
| Customer B isolation | **PASS.** Customer B authenticated successfully and did not see Customer A's workspace. A live PostgreSQL service check using Customer B's valid JWT denied access to Customer A's workspace. |
| Approvals / Board Pack aliases | **PASS.** The authenticated Approvals navigation opened `/approval_center` and showed Customer Approvals. Board Pack opened `/reports` and showed Evidence-linked Exports; both linked back to Customer Workspace. |
| Deferred Enterprise Registry URL | **PASS.** Direct `/enterprise_registry` navigation did not render the page and fell back to the app's page-not-found/login path. |

## Export transfer boundary

The browser confirmed export generation, persistence, approval linkage, package
contents through the live service, and the saved-package download control. A
Playwright download event was not captured when the saved-package control was
clicked. This is recorded as **download-transfer UX not independently
verified**, not as a failure of package generation or export authorization.
The release evidence does not claim that a browser-downloaded file was
inspected.

## Acceptance boundary

The authenticated customer workflow was executed end to end in one isolated
environment. PostgreSQL RLS/catalog checks and Customer B denial were performed
against that environment's live database. The separate FastAPI route-unmount
tests are not combined with this browser journey as a single deployment claim.
This result qualifies the local synthetic V1 route-freeze candidate only; it is
not hosted, commercial, or production acceptance.

