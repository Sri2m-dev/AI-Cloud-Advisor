# Nexora Production GA — Canonical Architecture

## Status

Program: Nexora Production GA  
Baseline: Nexora v1.1.0  
Certified Release SHA: f457f8afac89a1c196e9992a99e7b8b652182c7a

This document defines the canonical architecture authority for the
Nexora Production GA program.

It does not modify or supersede the certified Nexora v1.1.0 release.

---

## 1. Product Definition

Nexora is an Enterprise Technology Intelligence and Decision Platform.

Its purpose is to unify technology, financial, SaaS, operational,
business and governance evidence into a governed intelligence fabric
that supports executive visibility, enterprise analysis, decisions,
optimization and controlled execution.

Nexora must not evolve as a collection of independent dashboards.

Every production capability must belong to an explicit architectural
authority.

---

## 2. Canonical Architecture

The canonical production architecture is:

Executive Experience

        ↓

Enterprise Intelligence

        ↓

Ask Nexora / Decision Intelligence

        ↓

Enterprise Registry / Relationship Intelligence

        ↓

Enterprise Data Fabric

        ↓

Universal Evidence

        ↓

Source Facts

        ↓

Connector Platform

        ↓

Enterprise Source Systems

---

## 3. Canonical Product Experience

The primary production experience is persona-oriented.

Canonical executive and operational experiences include:

- CEO Workspace
- CIO Workspace
- CFO / Finance Workspace
- Enterprise Architect Workspace
- Operations Workspace
- FinOps Workspace
- Board / Leadership Experience

These experiences consume common governed platform capabilities.

Separate dashboards must not create independent data or business
logic authorities.

---

## 4. Enterprise Intelligence Authority

The `enterprise_intelligence` platform is the canonical intelligence
layer.

It is responsible for governed:

- enterprise queries
- search
- intelligence results
- decision context
- cross-domain intelligence

Legacy intelligence implementations may remain temporarily for
compatibility but must not become new independent authorities.

---

## 5. AI Authority

The strategic AI interaction surface is:

Enterprise Copilot / Ask Nexora

Canonical components include:

- enterprise_copilot
- governed Ask Nexora
- Universal Evidence governed intelligence
- semantic planning
- evidence-backed responses
- tenant-aware authorization
- decision intelligence

Older AI Copilot implementations are supporting or transitional
capabilities.

Unique functionality may be migrated into the canonical Enterprise
Copilot architecture before legacy implementations are retired.

No new independent AI assistant architecture may be introduced.

---

## 6. Enterprise Registry Authority

`enterprise_registry` is the canonical enterprise entity and
relationship authority.

It governs:

- canonical entities
- identity
- relationships
- relationship intelligence
- enterprise context
- versioned enterprise records

Legacy entity registry implementations must progressively converge
onto this authority.

---

## 7. Knowledge Graph Authority

The canonical Knowledge Graph is the Enterprise Registry-backed
knowledge graph.

Knowledge Graph capabilities must consume canonical entities and
relationships rather than establish an independent source of truth.

Technology Graph, Enterprise Graph, dependency views and relationship
explorers are projections or experiences over canonical enterprise
relationships.

---

## 8. Data Fabric Authority

`data_fabric` is the canonical semantic and persistence architecture
for enterprise information.

It governs:

- tenant context
- canonical entities
- identity resolution
- relationships
- lineage
- provenance
- data quality
- ontology
- semantic mappings
- temporal versioning
- atomic persistence
- idempotency

New enterprise data capabilities must integrate with the Data Fabric
rather than establish parallel persistence models without an explicit
architecture decision.

---

## 9. Universal Evidence Authority

`universal_evidence` is the canonical governed evidence architecture.

It governs evidence lifecycle capabilities including:

- ingestion evidence
- document evidence
- financial evidence
- governed measurements
- semantic interpretation
- authorization
- lifecycle state
- persistence
- auditability
- evidence-backed answers
- governed optimization
- production workflow

Universal Evidence must remain independent from presentation-layer
concerns.

---

## 10. Source Fact Authority

Connector-derived evidence must enter the governed architecture
through Source Facts or an explicitly approved equivalent ingestion
boundary.

`LiveSourceService` and Data Fabric SourceFacts represent the
canonical direction.

UI pages must not become source-of-truth ingestion authorities.

---

## 11. Connector Authority

The production Connector Platform is responsible for:

- source authentication
- source discovery
- ingestion
- normalization
- source health
- synchronization
- certification
- tenant isolation
- connector runtime operations

Existing connector frameworks must be consolidated rather than
duplicated.

AWS, Azure, GCP, Microsoft 365 and enterprise SaaS/observability
connectors must progressively use common connector contracts and
governed ingestion boundaries.

---

## 12. Financial Authority

Enterprise Spend and the governed Financial Data Fabric / Universal
Evidence financial architecture form the canonical financial
authority.

Executive financial experiences should present business-oriented
metrics such as:

- Total Technology Spend
- Cloud Spend
- SaaS / Software Spend
- Other Technology Spend
- Savings Opportunity
- Realized Savings
- Forecast
- Business / application / service attribution

Provider-specific AWS, Azure and GCP spend remains drill-down
information rather than the primary executive financial model.

---

## 13. Optimization Authority

`CanonicalOptimizationService` and its Universal Evidence production
optimization authority represent the canonical optimization path.

Optimization recommendations must be:

- evidence backed
- attributable
- governable
- approval aware
- measurable
- auditable

Parallel recommendation engines must be consolidated where they
represent the same business authority.

---

## 14. Governance and Execution

Execution must remain separated from recommendation and analysis.

Canonical execution must support:

- authorization
- approval
- validation
- safe execution
- audit events
- rollback
- outcome measurement

No AI or recommendation capability may directly bypass governance
controls for production-changing actions.

---

## 15. Navigation Authority

`components/sidebar_navigation.py` is the current route and
role-entitlement registry.

`components/navigation/sidebar.py` is the current navigation
presentation layer.

During Production GA these responsibilities may be refactored, but
route authority and presentation must remain explicitly separated.

---

## 16. Consolidation Policy

Production GA follows this rule:

> No new capability is created when an equivalent capability already
> exists in Nexora.

For an existing capability, Production GA must choose one of:

1. Promote
2. Consolidate
3. Adapt
4. Replace
5. Retire

Creating another parallel implementation requires an explicit
architecture decision.

---

## 17. Legacy and Consolidation Candidates

Known candidates requiring controlled review include:

- legacy AI Copilot surfaces
- Entity Registry legacy implementations
- duplicate Knowledge / Technology / Enterprise graph paths
- duplicate Digital Twin experiences
- duplicate executive dashboards
- Executive Dashboard V2
- legacy connector frameworks
- duplicate financial intelligence paths
- backup Python implementations
- historical views
- development/runtime residue

Classification as a candidate does not authorize deletion.

Removal requires dependency analysis, tests and a controlled work
package.

---

## 18. GA Product Surface Principle

Production navigation should expose business capabilities rather than
the internal history of Nexora development.

A production user should experience one coherent platform.

Internal services may remain modular, but users should not have to
understand which historical implementation provides a capability.

---

## 19. Production Authority Rule

Every GA capability must have:

- one canonical business authority
- one governed data authority
- defined tenant boundary
- defined authorization boundary
- defined persistence model
- defined observability model
- defined production test evidence

A capability without these properties is not Production GA complete.

---

## 20. GA Migration Sequence

The controlled migration sequence is:

GA-001 — Architecture Authority

GA-002 — Product Navigation Consolidation

GA-003 — Service and Data Authority Consolidation

GA-004 — Production PostgreSQL and Persistence Certification

GA-005 — Live Connector Production Certification

GA-006 — Integrated Browser and End-to-End UAT

GA-007 — Scale, Reliability and Operational Certification

GA-008 — Commercial Production GA Certification

---

## 21. Release Protection

Nexora v1.1.0 remains immutable.

Certified SHA:

f457f8afac89a1c196e9992a99e7b8b652182c7a

Production GA development must occur on the designated GA development
branch.

The v1.1.0 tag, certified artifact and closure evidence must not be
modified.

---

## 22. Architecture Decision

This document establishes the architecture baseline for Production GA.

Future Production GA work packages must identify the canonical
authority they modify before implementation begins.
