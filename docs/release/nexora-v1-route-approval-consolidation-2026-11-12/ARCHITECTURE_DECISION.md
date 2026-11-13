# NEXORA V1 Route and Approval Architecture

## Decision

Use the existing `CustomerWorkflowService` as the sole V1 approval authority.
Do not create or call the legacy `approval_requests` and `approval_history`
relations for the public V1 customer journey.

The customer workspace, Approval Center alias, Reports/export alias, and
authenticated approval API now use the same event workflow:

- Approval request and stage transitions are append-only customer-workflow
  events. The existing PostgreSQL contract and repository enforce transaction
  scope, JWT verification, tenant RLS, and authorization.
- The service enforces Finance → CIO → CEO (`executive`) stage order,
  requester/approver separation, role checks, decision linkage, and
  evidence references.
- Evidence export is allowed only after the final approval and creates a
  durable export event containing the approval history, decision, Ask result,
  and evidence reference. It does not expose plaintext evidence.
- The API derives organization, actor, role, and bearer token from the
  authenticated `get_current_user` result. Request selectors and compatibility
  actor fields cannot override that identity.
- G08 owner operations remain on their separate fail-closed authorization
  path. Ordinary customer approvals do not invoke G08 or use owner privileges.

The supporting contracts are in
[`customer_workflow_service.py`](../../../services/customer_workflow_service.py),
[`postgres_customer_workflow_repository.py`](../../../services/postgres_customer_workflow_repository.py),
and
[`001_customer_workflow_postgres.sql`](../../../database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql).

## Route decision

The runtime page registry is derived from
[`route_catalogue.csv`](../nexora-v1-m0-2026-11-07/route_catalogue.csv).
Only `SUPPORTED_CANDIDATE` pages with a matching role entry are registered.
`CONTROLLED_SUPPORTING` and `DEFERRED_NOT_PUBLIC_V1` pages are not registered.
The customer workspace is a narrowly scoped extension for the authenticated
workflow; approval and report pages are aliases into that service.

The route catalog contains **23 supported candidates, 8 controlled-supporting
pages, and 82 deferred pages**. The report's route policy does not certify the
candidate pages' underlying data contracts or product acceptance.

The principal implementation points are
[`v1_route_policy.py`](../../../auth/v1_route_policy.py),
[`app_main.py`](../../../app_main.py), and the backend route registries
[`backend/main.py`](../../../backend/main.py) and
[`api/v1/endpoints.py`](../../../api/v1/endpoints.py).

## Deliberate non-decisions

- No legacy SQL objects or speculative compatibility views were added.
- No customer, production, Supabase, or cloud resource was modified.
- No claim is made that every remaining supported-candidate page is database
  complete. The three unknown Cost Intelligence dependencies identified in the
  updated register remain blockers.
- The M0 catalogue's own metadata still says "proposed" and
  `NOT_CURRENTLY_CERTIFIED`; this implementation uses its route scopes per the
  current task instruction, but does not convert those labels into acceptance
  evidence.
