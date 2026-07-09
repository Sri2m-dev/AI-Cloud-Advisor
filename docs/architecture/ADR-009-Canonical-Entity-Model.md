# ADR-009: Canonical Entity Model

Status: Proposed
Date: 2026-07-09
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

Nexora receives overlapping records from cloud providers, SaaS platforms, ITSM, CMDB, finance, identity, and engineering systems. These records refer to the same real-world enterprise concepts with different identifiers, naming conventions, and completeness levels.

## Decision

Define a canonical enterprise model that every Data Fabric entity must inherit or implement.

Required metadata:

- UUID
- Canonical ID
- Source system
- Source identifier
- Created date
- Updated date
- Version
- Confidence
- Quality score
- Lineage
- Ownership

Initial canonical entity families:

- EnterpriseEntity
- BusinessCapability
- BusinessService
- Application
- Technology
- CloudResource
- SaaSApplication
- Vendor
- Contract
- CostCenter
- Department
- Owner
- Project
- Environment
- BusinessProcess
- Risk
- Recommendation
- Approval
- Policy
- Evidence

## Rules

- Canonical ID is stable across source-system changes.
- Source identifier is never treated as canonical identity.
- Entity metadata is provider-agnostic.
- Domain-specific fields extend the common entity contract without weakening it.

## Consequences

Connector outputs can be compared, merged, scored, and reasoned over through one entity contract. Dashboards and AI services stop depending on connector-specific schemas as their primary model.
