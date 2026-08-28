# PUE-ACT-007 Multi-Evidence Fusion & Identity Reconciliation

## Reused architecture

ACT-007 adds no registry, graph, CMDB, or materialization store. It uses the
ACT-006 `EnterpriseRegistryService` and the existing Data Fabric entity and
relationship registries. The Knowledge Graph remains the read-only projection
over canonical entities and relationships.

ACT-006 remains authoritative for canonical entity creation. ACT-007 only
reconciles independent governed source identities and creates process-local
source-to-canonical bindings.

## Source identity and matching

Each `SourceIdentityObservation` retains source system, source-native identity,
entity type, organization, tenant, prospect, analysis, source file, evidence
fingerprint, mapping decisions, normalization references, and optional
materialization reference. Source identities are never collapsed before
reconciliation.

Matching is deterministic and type-safe, in this order: canonical identity,
explicit cross-reference, exact native identifier, configured composite natural
key, governed alias, and human confirmation. Fuzzy names, co-occurrence,
monetary similarity, owner, region, and cost center alone cannot authorize a
binding. Entity type and complete scope are always part of identity.

## Proposals, decisions, and bindings

`ReconciliationProposal` preserves candidate canonical identity, source
identities, match method and keys, authority level, conflicts, governance and
normalization references, materialization references, and a deterministic
fingerprint. Ambiguous matches are `POSSIBLE_MATCH` until a human
`CONFIRM_MATCH` or `REJECT_MATCH` decision is recorded with actor, reason,
scope, target, timestamp, and decision fingerprint.

`SourceIdentityBinding` retains the complete scope, source identity, entity type,
canonical target, method, decision, evidence reference, and deterministic
binding fingerprint. Replays reuse the same binding. Existing canonical entities
are never duplicated or destructively merged.

## Conflicts and lifecycle

Conflicting source attributes remain `CONFLICT` when no configured authority
policy exists. `SourceAuthorityPolicy` is intentionally configurable and does
not embed assumptions such as CMDB or Finance supremacy. Existing bindings,
entities, and source provenance are not deleted when evidence or governance
becomes stale; affected pending proposals become `STALE` or `BLOCKED`.

ACT-C1 shadow and kill-switch states block binding execution without deleting
existing state. Audit events record proposal outcomes and binding creation using
scope and event metadata only, never raw evidence values.

## Scope and persistence

Organization, tenant, prospect, and analysis are part of every proposal and
binding. Prospect observations cannot bind to production entities or to another
prospect's entities. Bindings and decisions are process-local in this pilot and
do not survive restart; production persistence and reconciliation UX remain
reserved for ACT-009 and ACT-010.

## Fixture and workbook result

The controlled fixture uses separate AWS and CMDB resource identities plus
application catalogue and CMDB application identities. It converges to the
pre-existing canonical `Cloud Resource i-test123` and `Application Checkout`
without duplicate canonical entities, and preserves all source bindings.
The ambiguous `Payments` fixture remains governance-required until confirmed;
the distinct Application and Business Service names remain separate. Conflicting
owner descriptions remain visible without replacement.

`temp_uploads/CUR Jan 2026.xlsx` is one evidence source and cannot prove
cross-source reconciliation by itself. Its Service and Region values retain
their ACT-006 limitations; financial values remain observations and no
resources, applications, owners, or cross-source matches are invented.

## Integration and acceptance

The existing canonical registry and Knowledge Graph continue to expose one node
after successful fusion. No duplicate graph repository or dependency backend is
introduced. ACT-005 and ACT-006 behavior remains covered by their existing
tests. ACT-C7 is backend-certified; no browser acceptance is required because
ACT-007 adds no interactive production workflow. Integrated reconciliation UX
remains future work.