# Nexora Pilot Success Criteria

## Objective

Pilot success is measured by demonstrated customer value and governed evidence behavior, not by the number of Nexora capabilities shown.

## Mandatory Criteria

### Onboarding

At least one approved onboarding mode operates for the pilot:

- Zero-Access Evidence Import; or
- AWS Connected Mode when the required customer environment is available.

### Evidence Governance

Evidence must remain:

- customer and organization scoped;
- governed;
- traceable to provenance;
- represented through SourceFacts where supported;
- protected by applicable tenant/security boundaries.

### Intelligence

Nexora should demonstrate useful customer-specific intelligence in the agreed pilot scope.

Only evidence-supported findings count toward acceptance.

### Ask Nexora

Ask Nexora should:

- answer supported customer questions from governed evidence;
- preserve provenance;
- use available enterprise relationships;
- return UNKNOWN or qualified responses when evidence is insufficient.

Unsupported precision must not be fabricated.

### Decision Trace

At least one relevant finding, recommendation or decision-oriented workflow should be traceable to governed evidence.

### Security

The pilot must not require customer long-lived AWS access keys.

Cross-tenant access must not be introduced as an onboarding workaround.

### Customer Outcome

At closure, identify:

- demonstrated value;
- evidence gaps;
- environment prerequisites;
- confirmed defects;
- validated product gaps;
- next commercial or deployment step.

## Outcome Classification

### PASS

The agreed journey operates with governed customer evidence and mandatory criteria are met.

### CONDITIONAL PASS

The core journey succeeds but documented evidence or environment dependencies remain.

### PRODUCT DEFECT

An existing supported capability fails under valid pilot conditions.

### PRODUCT GAP

A legitimate customer requirement is not represented by the current product contract.

A product gap does not automatically create an implementation commitment.

### ENVIRONMENT REQUIRED

Validation requires customer or deployment infrastructure that is not yet available.

## Engineering Entry Rule

Engineering work should be opened only for:

- reproducible defects;
- security defects;
- material usability blockers;
- customer-validated requirements approved for the roadmap.

Pilot feedback must not trigger speculative platform expansion.
