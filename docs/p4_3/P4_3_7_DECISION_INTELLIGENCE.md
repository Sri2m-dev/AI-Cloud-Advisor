# P4.3.7 Governed Recommendation and Decision Intelligence

This increment adds deterministic Findings and prioritization above P4.3.4,
then adapts eligible proposals into WP-011. It reuses WP-009 queries, WP-010
evidence, WP-011 recommendation/decision lifecycle, WP-012 policy/approval, and
WP-013 execution/outcome verification. It creates no parallel authority system.

Findings are non-persistent projections with fact/inference separation,
confidence, exposure, evidence, lineage, provenance, freshness, and query
references. Priority is an explicit average of nine documented components.
Supported initial rules identify high-cost incomplete classification, high-cost
unowned entities, and classification conflicts.

Every proposal includes alternatives and limitations. AI uses `ActorType.AI` and
may create only a draft WP-011 Recommendation bound to an approved immutable
WP-010 package. Existing WP-011 rejects AI decisions and proposer self-approval.
Policy Preview uses the narrow ADR-022 amendment and is simulation only; it
cannot satisfy authorization or WP-013 execution.

Financial labels remain distinct: potential, approved, executed, and verified
realized savings. Only WP-013 outcome verification is authoritative for realized
value. For DEV account `727482365532`, the safe supported proposal is governance
and classification review; termination, rightsizing, migration, and
decommissioning are excluded while governed topology is absent.

Known limitations: the read-side center does not persist findings, materialize
evidence, or provide approval buttons. Existing Approval Center remains the
authority UX. Manual browser certification remains a P4.3 release gate.
