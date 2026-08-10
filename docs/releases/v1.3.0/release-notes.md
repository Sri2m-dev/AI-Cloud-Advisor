# v1.3.0 Enterprise Classification Engine Release Notes

## Summary

This release establishes Nexora's governed Enterprise Classification Engine on top of
the Enterprise Data Fabric and Cloud Account Registry. It completes P4.2 and provides
the immutable starting point for P4.3 Enterprise Intelligence Layer.

## Delivered capabilities

- Field-level inference with explainable confidence and evidence.
- Conflict detection, approval state, governed review, and persistence.
- Cloud account ownership/mapping resolution with versioned and reversible lifecycle.
- Registry and financial posture propagation without altering raw CUR facts.
- Multi-persona local authentication and canonical RBAC aliases.
- SQLite development fallbacks for audit, Leadership, Finance, Operations, Cloud Account
  Registry, and supported financial composition paths.
- Tenant-scoped Supabase repositories and production fail-closed configuration.
- Certified Administrator, CEO, CIO, CTO alias, Finance, Auditor, and Operations journeys.

## Release evidence

- Authoritative merge: `07525c351b8722a3b27b866f5f8b03cafdc27ecd`.
- Hosted CI: GitHub Actions run `31368283257`, passed on the merge SHA.
- Full suite: 818 passed, 2 skipped.
- P3: 94 passed.
- PVT-003: 60 passed, 2 skipped.
- Governance/certification: 40 passed plus both repository scripts.
- Ruff, compile/import, dependency integrity, and diff checks passed.
- Linked migration history: 17/17 aligned.

## Known boundaries

- Local SQLite certification proves application/runtime behavior, not live DEV financial
  posture.
- Existing dependency deprecation warnings remain non-blocking.
- The runtime SQLite database is an excluded local artifact.
- P4.3 functionality is not part of this release or certification branch checkpoint.

## Upgrade and rollback

Apply migrations only through the supported Supabase migration workflow and in version
order. Rollback remains governed by the released lifecycle, audit, and correction paths;
raw financial facts must not be rewritten. Reverting application deployment should use
the immutable release tag while preserving already-recorded audit and migration history.
