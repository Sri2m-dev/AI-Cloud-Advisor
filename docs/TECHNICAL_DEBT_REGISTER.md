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
| High | 1 |
| Medium | 2 |
| Low | 8 |

The expected target was Critical 0, High 0, Medium 2. Read-only hosted-workflow verification discovered a new High release-gate risk, so the target profile is not currently met.

## Register

| ID | Category | Debt | Status | Priority | Release effect | Recommended disposition |
|---|---|---|---|---|---|---|
| TD-001 | CI / Release | GitHub records zero-job failures for `background-jobs-cron.yml` and `cd.yml` on the certified head; feature-branch push did not run `ci.yml` | Open | High | Blocks merge approval | Correct workflow validation issues in a separately authorized CI phase, run hosted CI on the reviewed head, and require a successful check result. |
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

## Accepted qualifications

Relationship history is an accepted contractual deferral, not a failed validation. The Python 3.11 slotted-dataclass defect and the missing approval-service SLA API are resolved and are not open debt.

## Closure authority

Debt items may be closed only with evidence appropriate to their scope. TD-001 requires hosted GitHub Actions success, not only local command reproduction. TD-002 requires a reviewed contract and must not be solved by silently changing migration 0018. Documentation/legal items require the relevant governance owner.

