# Nexora v1.2 Technical Debt Register

## Governance

- Certification source baseline: `c8fcd2bf5f3548af4a08d5aef40a73722b18b6d5`
- Branch: `feature/p3-supabase-live-validation`
- Scope: debt remaining after P3.10 Phases 0–3
- Rule: this register records debt; Phase 4 does not remediate runtime, CI, Data Fabric, architecture, or feature behavior.

## Risk summary

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 9 |

The target release-risk profile is now met. Hosted CI run `29671495028` closed the former High workflow risk.

## Register

| ID | Category | Debt | Status | Priority | Release effect | Recommended disposition |
|---|---|---|---|---|---|---|
| TD-001 | CI / Release | Hosted workflow validation and feature-branch CI coverage | Resolved by run `29671495028` | Closed | None | Preserve the corrected triggers and `python -m pytest` invocation. |
| TD-002 | Data Fabric | Durable relationship-version history is intentionally deferred by migration 0018 | Accepted deferred scope | Medium | Does not invalidate P3, but constrains temporal relationship audit use cases | Define a compatible relationship-history persistence contract in a future approved program. |
| TD-003 | Quality Engineering | Full repository Ruff baseline has 775 findings and bare mypy is not reproducible with the current package/config layout | Open | Medium | Does not block current tests; limits broad static-quality enforcement | Establish bounded Ruff and mypy baselines without mass changes to certified code. |
| TD-004 | Archive | Thirty tracked archival placeholder `.py` files are not valid Python | Open | Low | Excluded from active compile/lint scope | Convert to non-source archival format after retention approval. |
| TD-005 | Runtime compatibility | Three Pydantic v1 validator deprecation warnings remain | Open | Low | No current failure; future Pydantic major release risk | Migrate validators in a focused compatibility change. |
| TD-006 | Documentation / Legal | Root `LICENSE` is missing | Open | Low | Requires owner/legal disposition before external distribution | Select and approve licensing terms; add the authoritative license file. |
| TD-007 | Documentation | `CONTRIBUTING.md` is missing | Open | Low | Contributor onboarding is incomplete | Add contribution, review, testing, and security-reporting guidance. |
| TD-008 | Documentation | No maintained Data Fabric API/RPC reference | Open | Low | Raises adoption and operator support cost | Generate or maintain a reference tied to contracts and migrations. |
| TD-009 | Documentation | Dedicated Data Fabric operator/troubleshooting guide is missing | Open | Low | Operational knowledge remains distributed | Consolidate safe operations, diagnostics, recovery, and escalation guidance. |
| TD-010 | Documentation | Connector Development Guide is missing | Open | Low | Provider extension conventions remain distributed | Document SDK contracts, certification, fixtures, and adapter lifecycle. |
| TD-011 | Repository hygiene | Historical and outdated documentation remains in active-tree locations | Open | Low | Readers can select superseded guidance | Move governed historical material to an archive and retain explicit status banners. |
| TD-012 | CI maintenance | `actions/checkout@v4` and `actions/setup-python@v5` emit Node.js 20 deprecation warnings while GitHub forces Node.js 24 | Open | Low | No current failure; future action-runtime maintenance | Upgrade action majors in a separately reviewed maintenance change when supported. |

## Accepted qualifications

Relationship history is an accepted contractual deferral, not a failed validation. The Python 3.11 slotted-dataclass defect and the missing approval-service SLA API are resolved and are not open debt.

## Closure authority

Debt items may be closed only with evidence appropriate to their scope. TD-001 is closed by hosted GitHub Actions run `29671495028`, not only local command reproduction. TD-002 requires a reviewed contract and must not be solved by silently changing migration 0018. Documentation/legal items require the relevant governance owner.
