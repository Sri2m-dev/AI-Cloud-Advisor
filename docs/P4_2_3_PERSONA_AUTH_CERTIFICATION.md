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

Automated in-app browser control is unavailable for this work package. This is the
required human worksheet; no row is claimed as executed.

| Persona | Login | Identity/role/org | Landing | Sidebar | Direct routes | Logout | Traceback | Screenshot |
|---|---|---|---|---|---|---|---|---|
| Admin | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Required |
| CEO | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Required |
| CIO | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Required |
| CTO alias | Pending | Pending | Pending | Pending | Pending | Pending | Pending | CIO/CTO required |
| Finance | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Required |
| Auditor | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Required |
| Operations | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Optional |

For every row verify displayed email, canonical role, `Default Org`, landing page,
allowed navigation, denied mutation controls, direct URL denial, logout, and no traceback.
This document does not authorize merge until manual results and screenshots are attached.

## Automated certification

Local certification on 2026-08-09 produced:

- persona/authentication, RBAC, FG-001, FG-002, P4.2, and audit fallback: 92 passed;
- PVT-003A/B/C: 60 passed, 2 environment skips;
- P3 gate: 94 passed;
- governance/certification: 40 passed plus both certification scripts;
- full repository suite: 797 passed, 7 expected skips;
- Ruff, compile/import, `pip check`, and `git diff --check`: passed.

Hosted CI is recorded on PR #42 after the exact certification commit is pushed.
