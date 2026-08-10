# P4.2.3 Multi-Persona Authentication and RBAC Certification

## Canonical active contract

The active Streamlit entrypoint is `pages/login.py`. Production uses the configured
Supabase provider and never enables SQLite authentication. Explicit non-production local
mode uses tenant-bound PBKDF2-SHA256 fixtures from `services/local_auth_service.py`.
The API `/auth/login` surface is separate and requires explicit `API_USERS_JSON`; it has
no implicit plaintext default users.

Canonical roles are lowercase values from `auth/role_constants.py`. `ceo` normalizes to
`executive`, `cto` to `cio`, and legacy organization/customer administrators to
`client_admin`. CTO remains a persona alias, not a separate RBAC role.

The legacy `utils.shared.login_page` and `shared.auth.login_user` surfaces are disabled.
Files under `patches/role-normalize` are historical patch evidence, not active runtime
authentication paths.

## Non-production personas

| Persona | Email | Canonical role | Landing page |
|---|---|---|---|
| Administrator | `admin@company.com` | `super_admin` | Executive Dashboard |
| CEO | `ceo@company.com` | `executive` | Executive Dashboard |
| CIO | `cio@company.com` | `cio` | CIO Dashboard |
| CTO alias | `cto@company.com` | `cio` | CIO Dashboard |
| Finance | `finance@company.com` | `finance` | FinOps Dashboard |
| Auditor | `auditor@company.com` | `auditor` | Audit Timeline |
| Operations | `operations@company.com` | `operations` | Operations Workspace |

Admin retains `admin123`. Other personas use the single documented non-production
fixture password `persona123`. Passwords are salted and hashed before SQLite persistence
and are never written to audit events.

## Authority matrix

| Role | Registry | Classification/account resolution | Approval authority |
|---|---|---|---|
| `super_admin` | Read/write/lifecycle | Resolve and correct | Yes |
| `executive` | Read | Read-only posture | No |
| `cio` | Read | Read/review posture | No |
| `finance` | Read/write | Mapping and resolution | No |
| `operations` | Read/write/lifecycle | Technical mapping and resolution | No |
| `auditor` | Read | Evidence/history read-only | No |

Navigation derives from the same canonical role normalization. Direct-route tests invoke
server-side `require_role` denial; hiding a sidebar entry is not authorization.

## Manual browser certification matrix

Automated in-app browser control was unavailable to the implementation agent. The
acceptance owner subsequently confirmed completion of the required manual browser
certification for every persona on 2026-08-09. The results below are recorded as
acceptance-owner-certified rather than agent-executed.

| Persona | Login | Identity/role/org | Landing | Sidebar | Direct routes | Logout | Traceback | Screenshot |
|---|---|---|---|---|---|---|---|---|
| Admin | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Captured |
| CEO | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Captured |
| CIO | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Captured |
| CTO alias | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Captured with CIO/CTO evidence |
| Finance | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Captured |
| Auditor | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Captured |
| Operations | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Completed |

Certification covered displayed email, canonical role, `Default Org`, landing page,
allowed navigation, denied mutation controls, direct URL denial, logout, and absence of
tracebacks. Manual evidence is complete; merge remains a separate reviewer decision.

## Automated certification

Local certification on 2026-08-09 produced:

- Leadership fallback: 10 passed;
- persona authentication/RBAC: 24 passed;
- audit fallback: 7 passed;
- FG-001: 18 passed;
- FG-002: 17 passed;
- P4.2 classification: 15 passed;
- PVT-003A/B/C: 60 passed, 2 environment skips;
- P3 gate: 94 passed;
- governance/certification: 40 passed plus both certification scripts;
- full repository suite: 797 passed, 7 expected skips;
- Ruff, compile/import, `pip check`, and `git diff --check`: passed.

Hosted CI run `31315164252` passed on persona implementation commit
`0048c06879f0346100de36d2df7131a3ae783e9f`. The final evidence descendant must also
pass PR #42 CI before release handoff.

## Leadership fallback reconciliation

Leadership fallback commit `a06ce8a8` is already an ancestor of the final P4.2 branch.
It contains exactly:

- `repositories/leadership_repository.py`;
- `services/leadership_composition.py`;
- `services/leadership_metrics.py`;
- `tests/test_leadership_repository.py`.

No runtime database artifact is included in that commit.
