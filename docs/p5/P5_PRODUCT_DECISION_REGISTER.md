# P5 Product Decision Register

Status: **APPROVED — PRODUCT GOVERNANCE BASELINE**

Approval authority: Product Owner under Product Governance v2.0

Effective date: 2026-08-14
Traceability: `docs/product/NEXORA_PRODUCT_FREEZE_V2_0.md`

This register preserves the original P5-D01–D14 identifiers. The approval package
used capability-oriented headings; the dispositions below map those policies back
to the original decision records so prior specifications and dependency tables
remain stable.

## Approved decisions

| ID | Original decision | Approved disposition | Status |
|---|---|---|---|
| P5-D01 | CEO measures/materiality | Use certified upstream business-service health, customer impact, financial exposure, security/regulatory exposure, and decisions requiring authority. Materiality is supplied by governed intelligence and is never inferred from cost alone. | APPROVED |
| P5-D02 | CIO measures/materiality | Use certified technology health, operational health, application/business-service exposure, architecture/technical-debt evidence, and governed decisions. UI does not calculate materiality. | APPROVED |
| P5-D03 | CFO measures/materiality | Use certified financial health, actual/budget/forecast outputs, allocation and reconciliation, vendor exposure, and governed value states. Projected value never appears as realized value. | APPROVED |
| P5-D04 | Enterprise Health policy | Display Technology, Financial, Security & Compliance, Operational, Business Service, and Governance dimensions. A composite may be shown only when a versioned, configured weighting policy is supplied by certified services. `UNKNOWN` never equals zero; missing data lowers confidence/coverage, not health. Always disclose score or state, confidence, and coverage. | APPROVED |
| P5-D05 | Business-service criticality | Vocabulary is Mission Critical, Business Critical, Important, Standard, and Non-Critical. The business service owns criticality; dependent infrastructure may inherit it through governed relationships. | APPROVED |
| P5-D06 | Forecast validity | Show confidence, freshness, coverage, and model version. Suppress the forecast value when the governed configurable confidence policy says it is unsupported. No numeric threshold is hard-coded in P5. | APPROVED |
| P5-D07 | Vendor concentration | Present certified concentration across spend, applications, business services, and critical workloads. P5 does not calculate concentration or invent recommendations. | APPROVED |
| P5-D08 | Technical debt | Present only certified evidence-based technical-debt outputs with trend, confidence, and coverage. No UI heuristic or duplicate formula is permitted. | APPROVED |
| P5-D09 | Executive urgency | Vocabulary is Critical, High, Medium, Low, and Informational. Urgency and recommendation order come from existing Decision Intelligence; P5 never guesses or independently reorders them. | APPROVED |
| P5-D10 | Board governance | Board artifacts are checkpointed, reviewed, approved, versioned, and signed. Draft artifacts are visibly watermarked. Audience, cadence, classification, retention, reviewers, and signatories are required governed inputs; absent inputs keep export/sign-off `UNSUPPORTED`. | APPROVED |
| P5-D11 | Evidence visibility | Executives receive summarized evidence, auditors complete entitled evidence, operations operational evidence, and finance financial evidence. RBAC, tenant, purpose, and field entitlements are enforced before composition and export. | APPROVED |
| P5-D12 | Narrative policy | Narratives preserve the order Facts → Evidence → Unknowns → Assumptions → Recommendations. Assumptions never appear as facts. AI may phrase or recommend but cannot approve, authorize, execute, or create authoritative decisions. Human decisions alone become authoritative. | APPROVED |
| P5-D13 | Product metrics/positioning | Track executive adoption, dashboard/search/AI usage, recommendation acceptance, and Board-report generation as aggregate product analytics only. No behavioral profiling or unapproved competitive claim is permitted. | APPROVED |
| P5-D14 | Browser release gate | Browser certification is a release gate, not an engineering gate. Engineering may implement, automatically certify, publish to the feature branch, and update PR evidence. When browser automation infrastructure is unavailable, the Product Owner may waive automation only after a documented manual functional review in a standard browser. Manual review evidence or an explicit Product Owner release disposition remains mandatory before merge, tag, or release. | APPROVED |

## Configuration and authority rules

- Health weights, materiality thresholds, forecast-confidence thresholds, and
  escalation thresholds are governed configuration supplied by authoritative
  services. They are not design tokens and are never hard-coded in P5.
- If an upstream model, policy version, entitlement, or required Board-governance
  input is absent, the UI renders `UNKNOWN`, `PARTIAL`, `UNAUTHORIZED`, or
  `UNSUPPORTED`; it does not manufacture a substitute.
- Recommendation ranking is preserved exactly as supplied by Decision Intelligence.
- P5 remains a non-authoritative presentation and composition layer over P4.3 RC1.

## Release disposition

P5.2 engineering is authorized under the previously approved RT1–RT8 release train.
No merge, release tag, or production rollout is authorized by this record. Manual
browser certification or the approved manual-review exception must be completed
before any such release action.
