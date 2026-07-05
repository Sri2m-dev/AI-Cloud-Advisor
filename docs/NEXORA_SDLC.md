# Nexora Software Development Lifecycle

Version: Z1.1.4
Status: SDLC governance baseline
Scope: How Nexora requirements, architecture, development, validation, certification, and releases move from idea to production.

## Objective

The Nexora SDLC ensures that every feature is delivered as part of a coherent enterprise platform. It prevents isolated implementation, undocumented behavior, duplicate logic, and unreviewed UI drift.

## Lifecycle Overview

```text
Requirement
    -> Architecture Review
    -> Blueprint
    -> Development
    -> Validation
    -> Certification
    -> Release
```

Every production-bound feature should move through this lifecycle.

## 1. Requirement

Requirements define the business outcome before implementation begins.

Each requirement should identify:

- Business problem
- Target user or role
- Expected decision or workflow
- Data sources
- Financial impact if applicable
- Risk, governance, or compliance impact if applicable
- Success criteria

Requirement flow:

```text
Business Requirement
    -> Architecture Review
    -> Blueprint
```

## 2. Architecture Review

Architecture review determines where the capability belongs in the platform.

Review questions:

- Which domain owns this capability?
- Which repositories and services should provide the data?
- Does it require Enterprise Financial Model integration?
- Does it require Knowledge Graph or Digital Twin integration?
- What RBAC roles should access it?
- What existing shared components should be used?
- What documentation must be updated?

No feature should proceed if it introduces duplicate business logic, duplicate financial logic, or page-specific design patterns when shared platform patterns already exist.

## 3. Blueprint

The blueprint translates the requirement into an implementation plan.

Blueprint contents:

- Scope
- Files to add or modify
- Services to consume
- Repositories to consume
- UI sections
- Evidence requirements
- Validation commands
- Regression surface
- Explicit files not to touch

Blueprints should keep changes small and isolated.

## 4. Development

Nexora development follows the repository -> service -> page model.

```text
Repository
    -> Service
    -> Page
```

### Repository

Repositories own:

- Source access
- Supabase queries
- Local or derived fallback behavior
- Schema normalization
- Defensive handling of missing tables or fields

### Service

Services own:

- Business logic
- Aggregation
- Derived metrics
- Relationship mapping
- Financial model consumption
- Recommendation preparation
- Empty-state-safe response shapes

### Page

Pages own:

- Composition
- Layout
- Rendering
- User interaction
- Evidence presentation

Pages should not own business logic, financial reconciliation, relationship derivation, or data access.

## 5. Validation

Validation confirms the feature works before certification.

Validation flow:

```text
Compile
    -> Smoke Test
    -> Route Test
    -> Regression Review
    -> Visual Review
```

Minimum validation:

- Python compile passes
- Route returns 200 OK
- No Streamlit traceback
- Empty state works
- Sidebar remains stable
- No completed pages regress
- No untracked local data files are committed

## 6. Certification

Certification confirms the feature meets platform standards.

Certification dimensions:

```text
Architecture
    -> UI
    -> Data
    -> Performance
    -> Security
    -> Financial
    -> Documentation
    -> Approval
```

Certification checks:

- Aligns with `NEXORA_PLATFORM_ARCHITECTURE.md`
- Aligns with `NEXORA_DESIGN_SYSTEM.md`
- Passes `NEXORA_UI_GOVERNANCE_CHECKLIST.md`
- Follows `NEXORA_RELEASE_WORKFLOW.md`
- Uses shared layout, cards, sections, evidence, and status language
- Uses `EnterpriseFinancialModel` where applicable
- Uses services instead of page-level business logic
- Handles RBAC and role-specific navigation
- Has no undocumented exceptions

## 7. Release

Release promotes certified work into a stable baseline.

Release flow:

```text
Tag
    -> Release Notes
    -> Documentation
    -> Production
```

Every release should include:

- Architecture updates
- SDLC compliance
- Design system compliance
- Regression completion
- Certification completion
- Release notes
- Release tag

## 8. Certification Status

| Status | Meaning |
| --- | --- |
| Certified | Meets architecture, UI, data, quality, documentation, and regression standards |
| Stable | Functional and usable, awaiting full standardization or certification |
| Development | Active implementation or active refinement |
| Prototype | Experimental, incomplete, or not production-ready |

## 9. Non-Negotiable Rules

- Do not modify completed pages during unrelated work.
- Do not duplicate financial calculations outside the Enterprise Financial Model.
- Do not introduce page-specific layout or cards when shared components exist.
- Do not bypass service-layer aggregation from page code.
- Do not mark a feature complete without documentation and validation.
- Do not promote a release without certification.

## 10. Completion Principle

No feature is complete until it is documented, standardized, regression-tested, and certified.
