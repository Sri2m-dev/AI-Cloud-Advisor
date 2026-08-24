# Nexora Engineering Standards Manual v1.0

Status: **v2.0 GOVERNANCE BASELINE — ENGINEERING CONFORMANCE REQUIRED**

Applies to: all new and materially changed Nexora code, tests, migrations,
configuration, UI, AI behavior, integrations, and release artifacts

## 1. Engineering charter

Engineering implements approved product behavior through secure, deterministic,
tenant-safe, evidence-aware, testable, and maintainable software. It does not make
undocumented product decisions.

The order of authority is:

1. security, privacy, legal, and authority ADRs;
2. released domain contracts and Product Freeze;
3. approved Product Decision Records and Architecture Decision Records;
4. bounded engineering work-package requirements;
5. implementation detail.

When requirements conflict or leave material behavior undefined, fail closed and
raise the missing decision. Do not invent a formula, threshold, entitlement,
authority, or customer-visible meaning in code.

## 2. Repository structure

### Ownership conventions

| Area | Responsibility |
|---|---|
| `data_fabric/` | Shared contracts, identity, tenancy, semantics, evidence foundations |
| Domain packages | Domain models, invariants, services, and owned interfaces |
| `services/` | Application orchestration and composition roots; no hidden authority |
| `repositories/` | Tenant-scoped persistence/projections; no business presentation logic |
| `connectors/` | Provider observation/runtime under connector safety policy |
| `pages/` | Thin Streamlit composition; no persistence, policy, or scoring logic |
| `components/` | Reusable visual/interaction primitives using the design system |
| `auth/` / `shared/` | Authentication, role normalization, shared application infrastructure |
| `tests/` | Contract, integration, security, regression, performance, and UI tests |
| `docs/` | Product, architecture, engineering, operations, certification, and release evidence |
| `migrations/` / `supabase/migrations/` | Versioned schema evolution only |

New top-level packages require architecture review. Names describe a stable domain
or platform capability, not a page, sprint, persona, or temporary implementation.

### Naming

- Python packages/modules/functions: `snake_case`;
- classes/contracts: `PascalCase`;
- constants/enums: `UPPER_SNAKE_CASE` values where externally frozen;
- request/result contracts: explicit `XRequest`, `XResult`, or `XResponse`;
- composition roots: `x_service(...)` or clearly named factory;
- tests: `test_<behavior>`, describing observable outcomes;
- migrations: ordered, immutable, and purpose-named;
- avoid `manager`, `helper`, `utils`, `new`, `final`, `v2`, or `temp` unless the
  abstraction/version is formally defined.

## 3. Dependency rules

```text
UI/pages → application services/composition → domain services/contracts
                                         → repository interfaces/adapters
                                         → authoritative stores/providers
```

- Domain code does not import pages or Streamlit.
- Contracts do not depend on repositories or provider SDKs.
- Pages do not instantiate repositories, run SQL, or call provider SDKs.
- Repositories do not call UI, AI providers, or encode persona presentation.
- Connectors do not own canonical enterprise or financial truth.
- Cross-domain dependencies use released contracts/services, not another domain's
  private persistence representation.
- Circular imports are prohibited; resolve ownership rather than hiding cycles.
- Composition roots are the only place runtime implementations/configuration are
  selected.

## 4. Contract standards

Public contracts must:

- require `TenantContext` or an authenticated tenant contract where applicable;
- identify canonical subject, tenant, version/checkpoint, and time context;
- use immutable inputs/outputs where practical;
- validate required fields, bounds, enums, timestamps, and authority invariants;
- expose partial/unknown/error semantics explicitly;
- preserve evidence, lineage, confidence, freshness, and assumptions when derived;
- be deterministic and serializable;
- use additive, backward-compatible evolution within a frozen release;
- require ADR/PDR and versioning for removal or semantic change.

Do not return unstructured dictionaries at a new public boundary when a stable
contract is required. Existing dictionary surfaces may be adapted incrementally
without breaking compatibility.

## 5. Service standards

Every service must have:

- one clear business/application responsibility;
- explicit dependencies supplied by composition, not hidden globals;
- mandatory tenant and authorization checks at the boundary;
- deterministic behavior for identical governed inputs;
- bounded depth, result count, fan-out, work, and/or timeout where traversal or AI is involved;
- no provider write or persistence side effect in a read/simulation service;
- explicit authority classification for derived outputs;
- stable failure semantics and no silent fallback that changes truth;
- no duplicated scoring, ranking, policy, financial, graph, or recommendation logic;
- tests for supported, partial, unknown, unauthorized, cross-tenant, and boundary cases.

Services must not obtain repositories or credentials through hidden imports inside
business methods. Runtime composition supplies them.

## 6. Repository standards

Repositories must:

- filter by organization and tenant on every read/write;
- fail closed when tenant scope cannot be proven;
- accept tenant context explicitly;
- parameterize queries and avoid dynamic SQL from user input;
- map persistence records to contracts at the boundary;
- define pagination/order deterministically for collections;
- preserve concurrency/version/idempotency rules;
- distinguish not found, conflict, validation, and infrastructure failures;
- avoid business scoring, narrative, UI formatting, or persona logic;
- expose no secrets in logs/errors;
- include tenant-isolation and cross-tenant rejection tests;
- use production fail-closed composition when authoritative configuration is absent.

Read-model repositories may cache projections but cannot become authoritative domain
stores. Cache keys include tenant, scope, checkpoint/model version, and entitlement
where output differs.

## 7. Tenancy, security, and privacy

- Authenticate before constructing application tenant context.
- Validate organization, tenant, persona, claims, and record scope at boundaries.
- Filter data before AI context assembly, caching, export, or telemetry.
- Never accept client-provided tenant IDs without matching authenticated membership.
- Use least-privilege credentials and provider permissions.
- No secret, token, credential, raw key, or sensitive prompt content in logs/tests/docs.
- Reject cross-tenant identity, relationship, evidence, scenario, report, and cache access.
- Security-sensitive fallbacks are explicit and fail closed.
- Authorization to view broad data does not imply authority to approve or execute.
- Threat modeling is required for new external inputs, AI tools, exports, provider
  writes, background agents, or authority-bearing workflows.

## 8. Evidence, lineage, and uncertainty

Derived behavior must preserve:

- fact versus derivation;
- authoritative source and canonical subject;
- checkpoint/version and time;
- evidence references and lineage;
- confidence, coverage, and freshness;
- assumptions, unknowns, and partial reasons;
- policy/model version;
- authority label.

Use the standard states `AVAILABLE`, `PARTIAL`, `STALE`, `CONFLICTED`, `UNKNOWN`, and
`UNSUPPORTED`. Missing data is not zero. Missing relationships are not no impact.
Unreconciled finance is not certified finance.

## 9. Financial engineering

- Financial Data Fabric remains authoritative for financial facts.
- Use explicit currency, billing/reporting period, decimal/rounding policy, and source.
- Preserve reconciliation and allocation state.
- Do not mutate authoritative financial state during query, AI, or simulation.
- Keep baseline, simulated, potential, approved, executed, and verified realized
  values distinct in contracts, tests, UI, exports, and narratives.
- Financial rules and thresholds require approved PDRs and Finance Governance review.
- Tests use exact certified examples plus boundary/rounding/multi-currency cases as applicable.

## 10. Authority and workflow engineering

The following are separate contracts and states:

```text
Finding → Recommendation Proposal → Scenario
→ Evidence Package → Human Decision → Policy Evaluation/Authorization
→ Execution → Verified Outcome
```

- AI cannot approve, authorize, or execute.
- Simulation is analysis-only and owns no execution port.
- A Recommendation Proposal is not a Decision.
- Policy preview is non-authoritative.
- Execution requires the released authority/evidence contracts.
- UI labels, APIs, logs, and tests must preserve these distinctions.
- Segregation of duties, effective/expiry time, version binding, and audit are mandatory.

## 11. AI engineering

Every AI feature must be:

- grounded in persona- and tenant-authorized structured context;
- cited with governed evidence;
- bounded in inputs, outputs, tools, latency, and cost;
- explicit about model provider/version and deterministic pre/post-processing;
- unable to change facts, ranks, assumptions, scores, or authority silently;
- robust to prompt injection and untrusted evidence content;
- able to abstain/refuse unsupported or prohibited requests;
- evaluated against golden supported, unsupported, adversarial, and authority cases;
- observable without logging secrets or sensitive raw prompts;
- separated from provider-write and execution capabilities unless a separately
  authorized architecture explicitly mediates them.

LLMs phrase and explain approved structured claims; they do not calculate material
business scores or become authoritative enterprise memory.

## 12. UI engineering

Every P5 page must:

- use the Executive shell and shared design-system components;
- be a thin composition over application/read services;
- contain no inline SQL, repository creation, scoring, policy, or financial logic;
- show scope, time, trust, evidence, unknowns, and authority appropriately;
- implement default, loading, empty, partial, stale, conflict, unknown, unsupported,
  unauthorized, and failure states as applicable;
- preserve filters/context through drill-down and exports;
- meet WCAG 2.2 AA and responsive requirements;
- avoid page-local CSS/tokens unless promoted through design-system governance;
- provide accessible alternatives for charts;
- use AppTest/browser and visual verification before certification.

Business rules belong in approved Decision Framework services, never components.

## 13. API and integration standards

- APIs use explicit versioned contracts and stable error envelopes.
- Validate size, type, enum, tenant, authorization, rate, and pagination bounds.
- Idempotency is required for retryable mutations.
- Correlation IDs span request, workflow, audit, and provider boundaries without secrets.
- Timeouts, retry, backoff, and circuit behavior are explicit and safe.
- Provider errors are translated without leaking credentials/internal details.
- Webhooks/events are authenticated, replay-safe, tenant-bound, and auditable.
- Deprecation includes migration guidance, telemetry, announced window, and tests.

## 14. Configuration and feature flags

- Configuration changes implementation behavior, not frozen product meaning.
- Secrets come from approved secret management, never repository files.
- Defaults are safe, explicit, and environment-aware.
- Production fails closed when mandatory authoritative configuration is missing.
- Feature flags cannot bypass PDR, authorization, evidence, or release governance.
- Flag state is tenant-safe, auditable, tested in both paths, and has an owner/removal date.

## 15. Database and migration standards

- Every schema change is a versioned reviewed migration; no manual Production DDL.
- Migrations are forward-safe, scoped, repeatable/idempotent where required, and tested.
- Tenant keys, constraints, indexes, RLS/grants, history/immutability, and rollback/forward
  recovery are explicit.
- Destructive changes require compatibility phases, backup/recovery evidence, and release approval.
- Append-only and authority records are never rewritten for convenience.
- Migration does not imply Production deployment authorization.

## 16. Observability and audit

Instrument latency, volume, errors, partial/unknown rates, evidence coverage, cache,
AI/tool use, and workflow state with bounded cardinality. Logs are structured,
tenant-safe, correlation-aware, and secret-free.

Audit records capture material mutations, authority transitions, model/policy
versions, evidence/report generation, and privileged access. Reading a dashboard
does not create a Decision.

## 17. Testing pyramid and required gates

Every work package selects applicable tests from:

1. contract/model unit tests;
2. repository tenant/persistence tests;
3. service/composition integration tests;
4. authority/security/adversarial tests;
5. deterministic replay and financial invariants;
6. performance P50/P95 at representative scale;
7. page AppTest/browser interaction tests;
8. visual regression and accessibility tests;
9. export native-render verification;
10. focused and full regression;
11. hosted CI on exact commit.

Tests must cover success plus partial, stale, conflict, unknown, unsupported,
unauthorized, cross-tenant, boundary, failure, and no-mutation behavior.

Do not weaken controls or assertions to meet performance targets. Flaky tests are
defects: assign an owner, root cause, and bounded remediation—not blind retries.

## 18. Code quality

- Python target and tooling follow `pyproject.toml`.
- Changed/certified scope passes Ruff; new violations are prohibited.
- Type hints are required for public contracts/services and nontrivial new code.
- Functions/classes remain cohesive; prefer composition over inheritance.
- Avoid mutable defaults, naive timestamps, uncontrolled randomness, and implicit globals.
- Time, IDs, and external clients are injectable where determinism/testing requires.
- Comments explain why/invariants, not restate code.
- Dead/duplicate code is removed only with compatibility and ownership review.
- Dependencies require necessity, license/security review, version control, and lock consistency.

## 19. Git and review standards

- Branches and commits are bounded to one authorized work package.
- Preserve unrelated user/runtime changes; stage explicit paths in mixed worktrees.
- Commit messages state the product/engineering outcome.
- No generated runtime databases, secrets, temp files, logs, or test artifacts.
- Review description includes requirements/PDR/ADR references, architecture impact,
  files/migrations, security/authority/evidence impact, tests, limitations, and rollout.
- Draft PR remains draft until release-owner readiness approval.
- No automatic merge, tag, or Production action unless explicitly authorized.

## 20. Documentation standards

Update documentation in the same commit as behavior. Required artifacts may include:

- PDR/ADR and contract/reference docs;
- operational/runbook and migration notes;
- model methodology/evidence semantics;
- UX/component and accessibility guidance;
- certification/performance/browser evidence;
- release notes and known limitations.

Documentation distinguishes implemented, certified, deferred, unsupported, and
planned behavior. Market claims require sourced approval.

## 21. Definition of Done

A work package is done only when:

- authorized scope and frozen Product/Architecture records are satisfied;
- no unresolved product decision was invented;
- tenant/security/evidence/financial/authority boundaries are proven;
- implementation is composed through owned services and contracts;
- applicable focused, regression, performance, UI, accessibility, export, and CI gates pass;
- migrations and Production impact are explicit;
- documentation and certification evidence are complete;
- exact local/remote/CI commit identity is verified when publishing is authorized;
- limitations and deferred gates are reported truthfully;
- merge/release/Production remain separate authorizations.

## 22. Exceptions and enforcement

An exception requires owner, rationale, risk, compensating controls, expiry, review,
and linked PDR/ADR/security record as applicable. Permanent standards changes update
this manual through governance; they are not accumulated as undocumented exceptions.

CI automates enforceable rules. Review checklists and certification cover semantic
rules. Repeated violations become platform/design-system improvements, not accepted
local patterns.

## 23. P5 engineering entry

P5.1 may begin only after Product Freeze v2.0 publication, PDR governance adoption,
the entry gates in the Product/UX specifications, and a bounded engineering package.
P5 implementation must reference exact Product Freeze sections and approved PDRs.
