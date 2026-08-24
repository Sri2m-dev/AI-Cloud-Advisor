# Nexora Decision Framework Specification

Status: **FROZEN CONSTITUTION v2.0 — BUSINESS RULES UNRESOLVED**

Implementation status: **NOT AUTHORIZED**

## 1. Purpose

The Nexora Decision Framework defines how governed enterprise facts become scores,
material changes, risks, priorities, narratives, recommendation rankings, executive
KPIs, and decision prompts.

It is a product-governance framework, not a replacement for P4.3 Query, Scenario,
Decision, Policy, Evidence, or Execution contracts.

## 2. Framework guarantees

Every decision model must be:

- deterministic for identical inputs, policy version, and checkpoint;
- tenant-scoped and persona-filtered only after shared truth is calculated;
- explicit about authoritative inputs and derived outputs;
- versioned, effective-dated, and reproducible;
- explainable at factor and evidence level;
- bounded and safe under missing, stale, conflicting, or partial data;
- calibrated and validated against representative enterprise cases;
- independent of LLM prose generation;
- incapable of granting approval, authorization, or execution authority;
- auditable from input checkpoint to displayed conclusion.

## 3. Canonical model contract

Each model specification must define:

```text
Model ID, name, owner, and purpose
Business question and personas served
Version, status, effective date, and review cadence
Canonical subjects and aggregation grain
Authoritative inputs and allowed derived inputs
Input freshness, quality, and evidence requirements
Normalization and unit/currency/period rules
Factors, weights, thresholds, caps, and exclusions
Missing, stale, conflicting, and unsupported behavior
Confidence and coverage calculation
Output values, labels, and materiality
Explanation template and factor contribution
Drill-down and evidence requirements
Authority classification
Validation cases, calibration evidence, and limitations
Change-control and rollback procedure
```

## 4. Standard output envelope

Every model returns a common conceptual envelope:

```text
result_id
model_id / model_version
tenant_context
subject / aggregation_scope
checkpoint / temporal_context
value / state / unit
materiality
factor_contributions
confidence / coverage / freshness
facts / derived_claims
evidence_references / lineage
assumptions / unknowns / partial_reasons
generated_at
authoritative = false (unless the underlying domain contract says otherwise)
```

A derived score is not an authoritative domain fact and cannot satisfy an execution
authority contract.

## 5. Model lifecycle

```text
DRAFT
→ DOMAIN REVIEW
→ SECURITY / DATA / MODEL-RISK REVIEW
→ APPROVED
→ SHADOW MODE
→ CALIBRATED
→ ACTIVE
→ MONITORED
→ REVISED or RETIRED
```

- Draft models cannot appear as production executive truth.
- Shadow mode compares outputs without influencing ranking or workflow.
- Activation requires versioned acceptance cases and approved thresholds.
- A revision creates a new version; historical outputs retain the old version.
- Rollback restores a prior approved version without rewriting history.

## 6. Uncertainty constitution

Every model must distinguish:

- `AVAILABLE`: supported by sufficient governed inputs;
- `PARTIAL`: supported conclusion with enumerated missing dimensions;
- `STALE`: previously valid inputs outside approved freshness;
- `CONFLICTED`: governed sources disagree without approved precedence;
- `UNKNOWN`: evidence cannot support a conclusion;
- `UNSUPPORTED`: no approved model exists for the question.

Missing data cannot be interpreted as healthy, zero risk, zero cost, no dependency,
or no impact. A model must state whether it abstains, produces a partial output, or
uses an approved conservative treatment.

## 7. Evidence and confidence

Confidence is not a decorative percentage. Its definition must identify:

- source reliability;
- evidence completeness;
- topology/classification/ownership coverage;
- freshness;
- reconciliation status;
- model applicability;
- conflict state.

Evidence weighting rules are product IP and require approval. An LLM confidence
score cannot substitute for enterprise confidence.

## 8. Materiality

Materiality determines whether a change becomes awareness, attention, a Finding, a
recommendation candidate, or an escalation. The model must support:

- absolute and relative magnitude;
- business criticality;
- affected scope and governed blast radius;
- persistence/duration;
- risk severity and trend;
- financial exposure;
- evidence confidence and freshness;
- persona relevance;
- decision due date and governance urgency.

Thresholds remain unresolved until approved by P5-D01–D03 and P5-D09. P5 presentation
must consume the approved result rather than recreating materiality rules.

## 9. Model portfolio

### DF-01 Enterprise Health

Question: What is the current overall enterprise posture?

Candidate dimensions: Business, Financial, Technology, Risk/Cyber, Governance, and
Data Trust. Whether a composite number is permitted, its weights, aggregation,
critical-floor behavior, and missing-data treatment are unresolved under P5-D04.

### DF-02 Business Health and Criticality

Question: Which business services and outcomes are materially exposed?

Candidate factors: approved service criticality, consumer scope, availability,
dependency concentration, ownership, financial exposure, incidents, lifecycle,
recovery evidence, and topology coverage. Vocabulary and ownership rules are
unresolved under P5-D05.

### DF-03 Financial Health

Question: Is the enterprise financially controlled and on plan?

Candidate factors: reconciliation, actual versus budget, approved forecast,
allocation, quarantine, commitments, renewal exposure, and verified value. Period,
variance, and forecast rules require P5-D03/D06.

### DF-04 Technology Health

Question: Is the technology estate resilient, supportable, and aligned?

Candidate factors: lifecycle, service health, operational evidence, standards,
dependency, ownership, security evidence, and business criticality. It cannot treat
missing monitoring or risk data as health.

### DF-05 Business Risk

Question: What business consequence may result from current exposure?

Risk is consequence plus likelihood/evidence where an approved model supports both.
It must retain affected service, owner, time horizon, exposure, controls, unknowns,
and evidence. No blast radius may be inferred from absent relationships.

### DF-06 Vendor Concentration

Question: Where does vendor dependence create material enterprise exposure?

Candidate factors: spend share, critical services supported, substitutability,
contract/renewal horizon, operational dependency, geographic/product concentration,
and evidence coverage. Entity resolution and thresholds require P5-D07.

### DF-07 Technical Debt

Question: Where does technology condition create material cost, risk, or change
constraint?

Candidate factors: lifecycle/support status, standards exception, reliability,
security evidence, maintainability, dependency, change friction, cost, and business
criticality. Definition and valuation require P5-D08.

### DF-08 Forecast Confidence

Question: How much reliance may an executive place on a forecast?

Candidate factors: approved model applicability, history length/quality, volatility,
seasonality support, reconciliation, known commitments, scenario assumptions, and
error calibration. Valid horizons and unsupported behavior require P5-D06.

### DF-09 Recommendation Priority

Question: Which evidence-backed recommendation deserves review first?

P4.3.7 `PriorityBreakdown` is the starting contract. Any added persona relevance,
materiality, urgency, value, effort, reversibility, or confidence factor must be
approved and must not become a second recommendation engine.

### DF-10 Executive KPI

Question: Which measure supports a named executive decision?

Every KPI follows the PDS KPI metadata contract. CEO, CIO, and CFO catalogs and
thresholds require P5-D01–D03. Inventory counts without a decision purpose are not
executive KPIs.

### DF-11 Narrative Selection

Question: Which structured claims belong in an executive brief, in what order?

Selection uses approved materiality, deterministic driver ranking, persona relevance,
novelty, unresolved decision state, confidence, and evidence. The LLM may phrase
selected claims but cannot select unapproved facts or alter ranking. Tone and review
requirements are P5-D12.

### DF-12 Decision Urgency

Question: When does an item require acknowledgement, review, decision, or escalation?

Candidate factors: materiality, criticality, due date, persistence, authority scope,
policy obligation, reversibility, affected scope, and owner response. Rules require
P5-D09 and cannot create a Decision automatically.

### DF-13 Evidence Visibility

Question: Which supporting facts may each persona view, export, or send to AI?

This is a field-level entitlement and purpose policy, not a score. It must filter
before context assembly and export. Rules require P5-D11.

### DF-14 Board Readiness

Question: Is a Board artifact complete and governed enough for sign-off?

Candidate gates: source checkpoints, reconciliation, required sections, evidence
resolution, unknown disclosure, narrative review, decision state, confidentiality,
reviewers, and integrity hash. Governance requires P5-D10.

## 10. Decision-to-model traceability

| Product decision | Framework models affected |
|---|---|
| P5-D01 CEO measures/materiality | DF-01, DF-05, DF-09–DF-12 |
| P5-D02 CIO measures/materiality | DF-01, DF-04, DF-06–DF-12 |
| P5-D03 CFO measures/materiality | DF-01, DF-03, DF-08–DF-12 |
| P5-D04 Enterprise Health | DF-01–DF-05 |
| P5-D05 Service criticality | DF-02, DF-04, DF-05, DF-09, DF-12 |
| P5-D06 Forecast validity | DF-03, DF-08, DF-10, DF-11 |
| P5-D07 Vendor concentration | DF-05, DF-06, DF-09–DF-11 |
| P5-D08 Technical debt | DF-04, DF-05, DF-07, DF-09–DF-11 |
| P5-D09 Executive urgency | DF-09–DF-12 |
| P5-D10 Board governance | DF-11, DF-14 |
| P5-D11 Evidence visibility | All models and exports |
| P5-D12 Narrative policy | DF-11 |
| P5-D13 Market positioning | External interpretation only; no model output |
| P5-D14 Browser release gate | Certification only; no model output |

## 11. Explanation contract

Every score or rank must answer:

1. What is the result?
2. Which approved model/version produced it?
3. Which factors contributed and by how much?
4. Which facts and evidence support each factor?
5. What changed from the comparison checkpoint?
6. What is missing, stale, conflicted, or unsupported?
7. How sensitive is the conclusion to assumptions?
8. What does the result permit—and explicitly not permit?

## 12. Validation and calibration

Each model requires:

- golden cases for healthy, warning, critical, partial, stale, conflict, unknown,
  unsupported, and cross-tenant rejection;
- boundary tests at every threshold;
- deterministic replay against fixed checkpoints;
- sensitivity and monotonicity tests where applicable;
- persona consistency tests;
- evidence and explanation completeness;
- financial invariants;
- authority non-escalation tests;
- domain-owner review against real historical decisions;
- shadow-mode comparison and false-positive/negative disposition.

Accuracy metrics must fit the model. A score should not claim statistical accuracy
when it is a policy index; a forecast requires calibrated error metrics; a ranking
requires relevance and decision-outcome review.

## 13. Change governance

Material changes include factors, weights, thresholds, source precedence,
normalization, missing-data behavior, labels, confidence, materiality, or explanation.
They require:

- new version and effective date;
- owner rationale and alternatives;
- impact analysis across personas and historical samples;
- security/data/model-risk review as applicable;
- regression and calibration evidence;
- documentation and release notes;
- rollback plan;
- explicit approval before activation.

## 14. Architecture boundary

The framework consumes frozen P4.3 contracts and emits versioned derived results.
It does not:

- own canonical entities, relationships, financial facts, or evidence;
- create another query, graph, scenario, recommendation, policy, or execution engine;
- persist authoritative domain state;
- let an LLM calculate material scores or rankings;
- create human Decisions or policy Authorizations;
- execute connector actions.

## 15. Entry gate for implementation

Decision Framework implementation begins only when:

- model owners are assigned;
- P5-D01–D12 have approved or explicitly deferred decision records;
- canonical input mappings and evidence requirements are reviewed;
- at least one end-to-end golden case is approved for CEO, CIO, and CFO;
- model lifecycle, registry, change control, and audit ownership are authorized;
- security, data governance, and model-risk reviews are complete;
- a bounded engineering package identifies which model is implemented first.

Until then, these are specifications and candidate factors—not product formulas.
