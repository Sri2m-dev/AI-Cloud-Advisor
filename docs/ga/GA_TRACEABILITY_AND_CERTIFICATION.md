# Nexora v2.0 GA Traceability and Certification

| Objective | Implementation surface | Evidence |
|---|---|---|
| Truthful metrics | Certification and workspace composition services | Integrity tests |
| Complete decision story | Shared Executive Experience | Yesterday-to-action review |
| Synthetic isolation | Demo tenant service and immutable JSON | Boundary tests |
| Persona readiness | Role navigation and tenant guard | Route, RBAC, and persona tests |
| Deployment | Docker, Compose, environment template | Packaging tests and rehearsal |
| Reports | Reports Center and backend | Generation and reconciliation |
| Customer readiness | GA and commercial guides | 45-minute and unaided reviews |
| Office exports | Governed reporting backend | PDF, PowerPoint, and Excel package tests |
| Connector runtime | Pinned AWS and Azure SDKs | Import and performance benchmark |

## Automated gates

- Full regression and tracked-source compilation
- Ruff critical checks and zero new violations on modified files
- Dependency, tenant, RBAC, demo-boundary, and packaging validation
- Hosted CI on the exact candidate commit
- `git diff --check`

## Current candidate evidence

- Full regression: **1,033 passed, 2 skipped**.
- Active-source compilation: **1,279 Python files passed**.
- Focused GA, security, integrity, and packaging tests: **13 passed**.
- Connector runtime imports: **PASS**.
- Performance benchmark: all nine named workloads within their configured targets; no
  benchmark execution errors. The benchmark's descriptive platform KPI panel is not a
  certified production-scale claim.
- Docker Compose deployment manifest: **PASS** (`config --quiet`).
- Ruff critical active-source gate and changed GA modules: **PASS**. Historical repository
  lint debt remains outside this bounded capability.
- Browser automation: **UNAVAILABLE** because the certification sandbox did not initialize;
  manual customer-browser certification remains a release-acceptance item.
- Hosted CI: **PASS** on implementation candidate `55901a04` for both push and
  pull-request workflows.

## Manual gates

- CEO, CIO, CFO, Architect, Operations, FinOps, Administrator, and Auditor journeys
- Five-minute executive questions for each major workspace
- Complete demonstration within 45 minutes
- Chrome and Edge; Firefox compatibility assessment
- Keyboard, focus, zoom, responsiveness, contrast, and text alternatives
- Standard unavailable and error states
- Report/export reconciliation
- Clean install, backup, restore, upgrade, and rollback rehearsal

## Release blockers

- Unresolved P0/P1 defect or supported-journey crash
- Tenant, RBAC, secret, database, or synthetic-data leakage
- Synthetic values presented as certified customer data
- Report values inconsistent with certified screens
- Hosted CI failure or missing recovery evidence
