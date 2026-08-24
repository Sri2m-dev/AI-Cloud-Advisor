# Nexora v2.0 RC2 Product Acceptance Report

Prepared: 2026-08-14

Status: **IN PROGRESS — EXTERNAL ACCEPTANCE GATES OPEN**

## Executive question

RC2 must determine whether a first-time CIO could confidently recommend a Nexora pilot.
The available evidence is not sufficient to answer yes yet. Engineering RC1 remains accepted;
the open items below are product, legal, commercial, and operational acceptance gates.

## Workstream results

| Workstream | Result | Evidence |
|---|---|---|
| Product acceptance | BLOCKED | Browser certification environment could not initialize; no visual, responsive, accessibility, or unaided journey PASS is claimed |
| Sales readiness | PARTIAL | Pitch, product brief, demo script, pricing hypotheses, ROI method, positioning, and FAQ are coherent; customer-facing CIO/CFO decks and an executable ROI calculator are absent from the active release tree |
| Demo enterprise | AUTOMATED PASS / VISUAL PENDING | Synthetic dataset is immutable, labeled, opt-in, restricted to `demo-*` tenants, and covers all three decision journeys; 15 focused tests passed |
| Release readiness | PARTIAL | Dependency integrity, role routing, packaging, Compose, CI, and rollback guidance pass; legal licensing and environment-backed recovery rehearsal remain open |

## Verified evidence

- RC1 full regression: 1,033 passed, 2 skipped.
- RC2 focused acceptance, isolation, security, and packaging tests: 15 passed.
- Dependency consistency: `pip check` PASS.
- Persona route smoke validation: PASS for authenticated and unauthenticated aliases.
- Hosted CI: PASS on final RC1 head `9d1254f2`.
- Docker build context excludes secrets, local databases, archives, backups, uploads, logs,
  exports, caches, and development environments.
- Product naming is normalized to **Nexora — Enterprise Decision Intelligence Platform** in
  the active README and GA commercial narrative.

## Release blockers

### RB-01 — Manual browser and accessibility certification

The controlled browser session failed before opening the application because its sandbox
could not initialize. Source inspection and automated tests cannot substitute for visual,
responsive, keyboard, focus, zoom, contrast, chart, and perceived-performance review.

Required closure: complete the published manual checklist in Chrome and Edge, record
screenshots and defects, and obtain a Product Owner disposition.

### RB-02 — Unavailable independent CIO acceptance

No independent executive has completed the unaided five-minute journey. Codex cannot act as
the first-time CIO because it built and inspected the product.

Required closure: a CIO/CTO or design partner must independently answer what to approve,
where risk exists, why spend changed, what action is next, and where the evidence resides.

### RB-03 — Legal licensing decision

The repository has no root `LICENSE`. Existing certification and technical-debt records
explicitly require a governance/legal decision before external distribution. Selecting a
license is a business/legal decision and is outside Codex authority.

Required closure: approve the distribution model and authoritative license or commercial
terms, then add the approved artifact before any external release.

### RB-04 — Sales-kit artifact completeness

The active release contains coherent source content but no current customer-facing CIO/CFO
presentation deck or executable ROI calculator. Historical PowerPoint files exist only in
excluded archive/backup locations and are not valid RC2 assets.

Required closure: authorize or provide the approved sales artifacts, then conduct a
sales-led 45-minute rehearsal using only the active release kit.

### RB-05 — Environment-backed recovery rehearsal

Backup, restore, upgrade, and rollback responsibilities are documented, but RC2 has no
current rehearsal evidence against the intended pilot environment. Automated source checks
cannot prove customer data restoration.

Required closure: the environment owner records backup identifiers, restoration evidence,
artifact rollback, post-restore tenant/authentication/financial/audit smoke results, and
named operational owners.

## Non-blocking v2.1 backlog

- Migrate three Pydantic v1 validators before a future Pydantic major upgrade.
- Establish a bounded repository lint-debt baseline without reopening frozen product code.
- Continue archive/documentation hygiene outside the customer release package.
- Generate customer-feedback priorities only after pilots; do not add speculative features.

## RC2 disposition

RC2 remains open. No architecture or capability work is justified. GA must not be authorized
until RB-01 through RB-05 are closed or explicitly waived by the appropriate Product, Legal,
Commercial, and Operations owners.
