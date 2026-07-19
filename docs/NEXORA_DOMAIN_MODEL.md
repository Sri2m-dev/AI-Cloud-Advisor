# Nexora Domain Model

Status: Current canonical domain direction with explicit P3 foundation boundary
Program: P3 Enterprise Data Fabric & Intelligence Platform
Date: 2026-07-09

## Canonical Domains

| Domain | Primary Entities |
| --- | --- |
| Business Architecture | BusinessCapability, BusinessService, BusinessProcess, Department, Owner |
| Application Portfolio | Application, Project, Environment, Owner, BusinessService |
| Technology Portfolio | Technology, CloudResource, SaaSApplication, Vendor, Contract |
| Financial Model | CostCenter, Contract, Vendor, Project, Department |
| Risk and Governance | Risk, Policy, Approval, Evidence, Recommendation |
| Operations | Environment, CloudResource, Application, Incident evidence, Recommendation |
| Intelligence | EnterpriseEntity, EnterpriseRelationship, SemanticConcept, QualitySignal |

## Core Relationships

```text
Application runs_on CloudResource
Application owned_by Department
Technology supplied_by Vendor
BusinessService depends_on Application
CostCenter funds Technology
Risk impacts BusinessService
Recommendation targets EnterpriseEntity
Policy governs EnterpriseEntity
Evidence supports Recommendation
Owner accountable_for EnterpriseEntity
```

## Relationship Rules

- Relationships are canonical and extensible. Mutable relationship revisions are supported; durable relationship-version history is deferred under migration 0018.
- Relationships carry confidence, provenance, and lineage.
- Direction and cardinality are explicit.
- Provider-specific relationships are normalized into enterprise relationship types.

## Semantic Examples

```text
AWS EC2
Azure VM
GCP Compute Engine
  -> Virtual Machine

AWS S3
Azure Blob Storage
Google Cloud Storage
  -> Object Storage
```

## Quality Dimensions

Every entity and relationship can be evaluated for completeness, freshness, accuracy, consistency, validity, trust score, owner, and last verified timestamp.

## AI Consumption Rule

AI systems should consume canonical entities, canonical relationships, semantic concepts, lineage, provenance, and quality scores. They should not reason directly over raw connector tables except as cited evidence.
