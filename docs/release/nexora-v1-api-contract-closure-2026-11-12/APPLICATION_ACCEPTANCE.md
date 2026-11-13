# Application Acceptance

## Evidence boundary

The current task's targeted run passed **65 tests, 0 failed and 0 skipped** in
72.89 seconds. Its fresh local PostgreSQL test replays the existing 43-input
chain and executes the synthetic customer-workflow service contract. This is
service-level evidence for that separate namespaced workflow, not an end-to-end
acceptance of the full application or the 29 legacy database objects.

## Journey status

| Capability | Evidence in this task | Acceptance status |
|---|---|---|
| Existing authentication and JWT/tenant security tests | Included in 65-pass targeted suite | Existing covered behavior passes; not a new browser session |
| Namespaced customer workflow persistence | Fresh-cluster bootstrap/service test included in 65-pass run | Service-level pass; does not establish legacy-object compatibility |
| Legacy approval page and durable approval history | Callers use `approval_requests` and `approval_history`; full contracts unresolved | Not accepted |
| Approval queue dashboards | Multiple repository callers use `approval_queue`; scope and semantics unresolved | Not accepted |
| Cost, reports and mart-backed APIs | `cost_intelligence` and `reports` are supported candidates; mart output contracts unresolved | Not accepted |
| Connector and cloud connection pages | Proposed deferred routes, but direct route restriction is unfinished; persistence is opt-in | Not accepted as safely deferred |
| Background notifications/KPI refresh | Background jobs default off; V1 profile enforcement is absent | Not accepted as safely disabled |
| Customer A/B security for the 29 objects | No authoritative object contracts to test | Not verified |
| Full FastAPI/Streamlit startup against a database containing the 29 objects | Not run | Not verified |
| Authenticated browser route-denial checks for deferred pages | Not run; M0 says direct-route enforcement remains unfinished | Not verified |

## Conclusion

The qualified namespaced service workflow must not be combined with the
unqualified legacy routes into one full-application acceptance claim. A
supported route list, enforceable direct-route guards, authoritative database
contracts and integrated API/browser tests are prerequisites to application
acceptance.
