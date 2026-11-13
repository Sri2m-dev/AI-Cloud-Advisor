# Security Test Results

## Executed evidence

The targeted run for this task completed with **65 passed, 0 failed, 0
skipped** in 72.89 seconds. It covered the existing schema-contract,
authentication/tenant-security and approval tests, plus the isolated
fresh-cluster customer-workflow bootstrap/service test.

The run confirms the exercised existing behavior only. It does not show that
the 29 legacy relations exist, that their RLS/grants are configured, or that
the full app's legacy routes have been isolated for V1.

## Findings

- Existing JWT-bound tenant authorization remains the baseline; no
  default-tenant fallback or authorization weakening was introduced.
- The dedicated namespaced V1 customer-workflow test remains separate from
  legacy `approval_requests`, `approval_history`, and `approval_queue`.
- The current alerts API route selects `alert_executions`, contrary to the
  older SC-001 `LEGACY_UNREACHABLE` disposition. The object is classified
  UNKNOWN pending route and contract resolution.
- Connector database persistence is opt-in through
  `NEXORA_CONNECTOR_PLATFORM_DB`; in-memory defaults do not prove durable
  storage. Background jobs default off through `BACKGROUND_JOBS_ENABLED`, but
  neither flag is a V1 product-profile enforcement boundary.
- The proposed M0 route catalogue is not enforced. It says current navigation
  is broader and direct-route restriction remains work. No negative
  direct-route/access test for the full V1 allowlist was executed.
- No object-level JWT spoofing, A/B RLS, grants, ownership or
  `SECURITY DEFINER` validation can pass for undefined contracts; these remain
  explicit acceptance tests, not claimed results.
- No plaintext evidence or secret exposure was introduced by this
  documentation-only closure. No credentials, real customer data or external
  service were accessed.

## Required security acceptance before GO

For each retained relation/function: verify owner, role grants, runtime role,
JWT-derived tenant binding, RLS (including view security behavior), cross-tenant
denial, unauthorized mutation rejection and controlled missing-object failure.
For every deferred route/job: verify direct URL/API denial and absence of
background execution under the approved V1 profile. For credentials, prove
secret-reference-only handling and redaction.
