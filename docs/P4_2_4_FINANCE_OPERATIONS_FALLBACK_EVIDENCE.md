# P4.2.4 Finance and Operations Local Repository Fallback

## Runtime composition

Finance now resolves all landing-page inputs through `TechnologySpendService` and the
technology-spend composition. Operations resolves its landing-page inputs through
`OperationsWorkspaceService` and the operations-workspace composition.

In either domain, a valid Supabase URL and credential select the tenant-filtered
Supabase adapter. Missing, placeholder, or invalid configuration selects SQLite in
non-production. Production with invalid configuration raises a domain-specific
configuration error. Local optional marts that are missing or lack a recognized tenant
column return an empty result. Supabase optional or legacy marts that cannot satisfy the
explicit organization filter also return empty; they are never retried unscoped.

The Finance page no longer calls the shared Supabase proxy or reporting service. Its
spend, budget, forecast, recommendations, and executive-summary reads share one
repository boundary. The Operations page contains no direct Supabase read. RBAC remains
enforced by each page before repository composition, and every repository call requires
an organization identifier.

## Active persona landing-path audit

The canonical Executive, CIO, CTO alias, Finance, Auditor, Operations, and Leadership
landing pages contain no direct `supabase.table(...)` invocation. Some certification
services behind Executive/CIO and the audit service retain guarded legacy Supabase
adapters with existing fallbacks; they are not hard local-runtime dependencies. Direct
Supabase consumers remain elsewhere in the wider application, outside these persona
landing paths and outside P4.2.4 scope.

## Automated certification

- Finance/Operations fallback: 16 passed;
- Leadership fallback: 10 passed;
- persona authentication/RBAC: 19 passed;
- audit fallback: 7 passed;
- FG-001 registry and local authentication: 23 passed;
- FG-002 account resolution: 17 passed;
- P4.2 classification: 15 passed;
- PVT-003A/B/C: 60 passed, 2 expected skips;
- P3 gate: 94 passed;
- governance/certification: 40 passed plus both certification scripts;
- full suite: 818 passed, 2 expected skips; 820 collected;
- Ruff critical checks, compile/import, `pip check`, and `git diff --check`: passed.

## Browser certification status

The automated Streamlit AppTest checks prove that Finance and Operations render with
local authentication, no Supabase configuration, and no traceback. In-app browser
control was unavailable because the browser runtime rejected its sandbox metadata
before opening a tab. Manual screenshots are therefore still required for:

- `finance@company.com` / FinOps Dashboard;
- `operations@company.com` / Operations Workspace;
- `auditor@company.com` / Audit Timeline regression.

This local certification validates UI/runtime behavior only. It does not certify real
DEV financial values or Supabase data posture.
