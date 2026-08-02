# FG-001 Cloud Account Registry evidence

## Navigation remediation

`app_main.py` authenticates and redirects to a role default page. Each page
then calls `components.navigation.sidebar.render_enterprise_sidebar` with
`PAGE_PATHS` and `ROLE_PAGES` from `components.sidebar_navigation`.

The original FG-001 change registered the route in `PAGE_PATHS` and appended
it to `ROLE_PAGES`. That was insufficient because non-super-admin personas are
rendered from `SIMPLIFIED_ROLE_NAVIGATION`, which ignored the appended role
entry. The long-running Streamlit process also retained the previously
imported page registry until its watched navigation dependency was reloaded.

The remediation registers Cloud Account Registry in the established
simplified navigation for Executive, CIO, and Finance, while the full registry
serves Super Admin and Client Admin. Auditor receives an explicit read-only
role list. Technical and Viewer do not receive the page. No parallel
navigation framework was introduced.

## Authorization and data boundaries

- Full lifecycle: `super_admin`, `client_admin`, `operations`.
- Create/update/import: `finance` plus full-lifecycle roles.
- Read: full/edit roles plus `executive`, `cio`, and `auditor`.
- Unauthorized roles are rejected by the service even if they invoke it
  without a visible button.
- Repository operations require `AuthenticatedTenantContext` and apply both
  `organization_id` and `tenant_id` filters.
- Database uniqueness is `(organization_id, tenant_id, provider, account_id)`.
- RLS uses authenticated organization membership; delete is revoked.
- Audit records are tenant-scoped and append-only to application roles.

## Validation evidence

Synthetic tests cover navigation regression, normalized role visibility,
tenant-scoped CRUD, duplicate rejection, deterministic governance scoring,
audit old/new values and reason, preview-before-commit CSV import, CSV/XLSX
exports, archive/deactivate without hard delete, and unauthorized denial.

DEV migration `202607310002_cloud_account_registry.sql` is deployed. Browser
certification uses synthetic accounts `999999999999` and `888888888888`; they
must be archived after certification while their audit evidence remains.

Production was not accessed. No CUR facts or account mappings were changed.
