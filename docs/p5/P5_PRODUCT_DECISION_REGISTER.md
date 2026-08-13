# P5 Product Decision Register

Status: **OPEN — PRODUCT DESIGN REQUIRED**

This register converts the Executive Intelligence blueprint into explicit decisions.
Engineering must not choose these business rules implicitly.

| ID | Decision | Proposed owner | Required output | Status |
|---|---|---|---|---|
| P5-D01 | CEO first-view measures and materiality | CEO sponsor + Product | Five measures, thresholds, comparison period | OPEN |
| P5-D02 | CIO first-view measures and materiality | CIO sponsor + Product | Five measures, thresholds, portfolio scope | OPEN |
| P5-D03 | CFO first-view measures and materiality | CFO sponsor + Finance governance | Five measures, periods, variance thresholds | OPEN |
| P5-D04 | Enterprise Health policy | Risk + Data Governance | Dimensions, weights or no composite, missing-data treatment, version | OPEN |
| P5-D05 | Business-service criticality | Business Architecture | Vocabulary, ownership, criticality and impact rules | OPEN |
| P5-D06 | Forecast validity | Finance + Model Risk | Approved horizons, models, confidence and unsupported behavior | OPEN |
| P5-D07 | Vendor concentration | Procurement + Risk | Entity definition, materiality, dependency and escalation rules | OPEN |
| P5-D08 | Technical debt | CIO + Enterprise Architecture | Measures, lifecycle policy, value/risk interpretation | OPEN |
| P5-D09 | Executive urgency | Governance + Executive sponsors | Attention ranking, due dates, escalation, acknowledgement | OPEN |
| P5-D10 | Board report governance | Company Secretary + Security | Audience, cadence, classification, sign-off, retention | OPEN |
| P5-D11 | Evidence visibility by persona | Security + Data Governance | Field-level entitlement and export rules | OPEN |
| P5-D12 | Narrative policy | Communications + Legal + AI Governance | Tone, length, disclaimers, human review and attribution | OPEN |
| P5-D13 | Market positioning | Product Marketing + Legal | Sourced comparison method and approved external claims | OPEN |
| P5-D14 | P4.3 manual browser gate | Release owner | Pass evidence or formal release disposition | OPEN |

## Persona workshop prompts

Each sponsor should answer using real decisions from the last quarter:

1. What did you need to know but could not obtain quickly?
2. Which five signals changed a decision?
3. What is awareness versus required action?
4. What amount or risk is material?
5. Which words do you use for the issue?
6. What evidence makes you trust or reject the conclusion?
7. Where should the drill-down stop for your role?
8. What belongs in a board pack but not the live workspace?

## Required artifacts before P5.1

- approved CEO, CIO, and CFO first-viewport wireframes;
- one golden-path story for a cost increase;
- one golden-path story for business-service degradation;
- one incomplete-topology/unknown-data story;
- one recommendation-to-scenario-to-human-decision story;
- Board Report outline with sign-off and confidentiality rules;
- field-level persona entitlement matrix;
- versioned health and materiality policy decisions;
- usability findings and disposition log.

## Decision record template

```text
Decision ID:
Owner:
Approved date:
Business question:
Chosen rule:
Alternatives rejected:
Materiality/threshold:
Data and evidence required:
Unknown/missing-data behavior:
Persona visibility:
Authority impact:
Version/effective date:
Review cadence:
```
