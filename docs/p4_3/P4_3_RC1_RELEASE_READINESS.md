# v1.4.0 Enterprise Intelligence RC1 Readiness

## Scope

P4.3.1 through P4.3.8 are consolidated. P4.3.9 is intentionally not started.
No Production access, schema migration, merge, or authority expansion is part of
this checkpoint.

## Consolidation audit

| Area | Result |
|---|---|
| Contract ownership | PASS — freeze catalog documents the public boundaries. |
| Duplicate services | PASS WITH DEFERRAL — compatibility surfaces are classified; destructive removal deferred. |
| Runtime composition | FIXED — standard Copilot composition now wires governed Scenario Intelligence. |
| Tenant isolation/RBAC | PASS — mandatory context checks and persona tests cover query, search, Copilot, decision, and scenario layers. |
| Evidence propagation | PASS — canonical references, governed edge evidence, partial/unknown states, and financial source attribution remain visible. |
| Authority separation | PASS — reasoning and simulation own no Approval, Authorization, or Execution mutation. |
| Financial semantics | PASS — potential, approved, executed, and verified realized values remain distinct. |
| API stability | PASS — RC1 freeze permits additive compatible changes only. |

## Release gates

- Full suite, scoped Ruff, compile/import, `pip check`, and `git diff --check` must pass on the final RC1 commit.
- Hosted CI must pass on the exact pushed SHA.
- PR #43 must remain open, draft, unmerged, target `main`, and be mergeable.
- Manual browser matrix remains a consolidated release gate and must not be reported as passed without screenshots/inspection.

## Known limitations

- Historical reconstruction is explicitly unsupported where source domains lack a valid as-of model.
- Zero-edge topology produces an incomplete result rather than inferred impact.
- Risk remains unknown when governed risk evidence is absent.
- Legacy Simulation Center remains available until a separately authorized compatibility removal.
- Manual browser certification remains pending from P4.3.8.

## Recommendation

Once final local and hosted RC1 gates pass, the foundation is stable enough to
begin P4.3.9 Executive Intelligence. P4.3.9 should consume these frozen contracts
and add presentation/composition only; it should not introduce another registry,
graph, query, scenario, recommendation, or authority framework.
