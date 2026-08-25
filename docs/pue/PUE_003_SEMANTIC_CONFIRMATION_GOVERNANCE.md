# PUE-003 — Semantic Confirmation Governance

Status: implementation candidate for PUE-C3 review

Authority: shadow and non-authoritative

Depends on: PUE-002A scoped semantic discovery provenance

## Purpose

PUE-003 governs decisions about PUE-002 semantic candidates. It records whether
a candidate was automatically accepted, human-confirmed, rejected, overridden,
superseded, or expired. It does not normalize evidence or grant aggregation,
entity, graph, query, or AI-answer authority.

The lifecycle is:

```text
semantic candidates
  → versioned governance policy
  → confirmation requirement / pending request
  → authorized decision
  → append-only history and effective semantic mapping
```

## Scope authority

Every confirmation request and mapping decision copies these fields directly
from `SemanticDiscoveryProvenance`:

- `analysis_id`
- `prospect_id`
- `organization_id`
- `tenant_id`
- `source_id`
- `file_id`
- `sheet_id`
- `column_id`

No caller supplies a replacement scope. The service does not consult Streamlit
state, filenames, databases, globals, request context, or the current user's
tenant. Legitimately absent organization or tenant identifiers remain absent.
Consequently, a prospect-only decision cannot acquire organization or tenant
scope from the reviewing application session.

The complete scope tuple partitions pending requests, decision history, and the
effective mapping. A decision for one analysis, prospect, file, sheet, or column
is not visible as an effective decision for another.

## Contracts

`ConfirmationRequirement` records the versioned policy result and its reasons.
`ConfirmationRequest` is an idempotent pending request bound to a discovery,
candidate, scope, classifier, ontology, and policy version.

`MappingDecision` is immutable and retains:

- the selected ontology concept;
- decision and confirmation states;
- actor identity, principal, role, and actor type;
- timestamp and required reason where applicable;
- the original candidate ranking;
- structural and semantic fingerprints;
- classifier, ontology, discovery-policy, and governance-policy versions;
- supersession and effective-period references.

`MappingDecisionHistory` is append-only. `EffectiveSemanticMapping` is a view of
the currently effective decision, not normalized evidence.

## State and policy rules

- High-risk, restricted, ambiguous, or otherwise non-auto-classified candidates
  require confirmation.
- Auto-acceptance is limited to policy-eligible, low/moderate-risk candidates
  already marked `AUTO_CLASSIFIED` by PUE-002.
- Confirm and reject are human actions protected by role policy.
- Reject and override require an explicit reason.
- Override requires a privileged role and an ontology-approved concept.
- Rejection and expiry remove the effective mapping; they never create a
  fallback mapping.
- Override appends an explicit `SUPERSEDED` history event before the new
  `OVERRIDDEN` decision. Prior records are not mutated or deleted.
- Repeated identical requests and decisions are idempotent.
- An effective mapping cannot transition back to a pending request.

Audit events contain decision metadata and scope, but no raw evidence values or
representative samples.

## Drift and retention

An effective decision requires reevaluation when its semantic fingerprint,
classifier version, ontology version, discovery-policy version, or governance
policy version differs from the current discovery or policy. Expiry is an
explicit immutable decision and removes the effective mapping while preserving
history for the surrounding prospect retention and audit mechanism.

PUE-003 uses an in-memory repository and audit sink deliberately. It introduces
no production database, migration, UI, or cross-analysis learning behavior.

## Explicit non-goals

PUE-003 does not provide:

- normalized fields or normalized values;
- monetary or other aggregation;
- query capability;
- enterprise entities or graph relationships;
- recommendations or decision intelligence;
- Ask Nexora answers;
- changes to the accepted prospect intake authority or experience;
- reuse of one analysis decision as training or authorization for another.

Those capabilities remain gated behind later PUE certification stages.
