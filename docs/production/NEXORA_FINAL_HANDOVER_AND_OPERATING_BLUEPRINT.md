# NEXORA FINAL HANDOVER & OPERATING BLUEPRINT

## Document Status

Program: Nexora Enterprise Technology Intelligence & Decision Platform

Status: FINAL LOCAL PRODUCT HANDOVER

Core Product: READY

Operating Model: Local-first, cloud-portable

Production Activation Branch: program/nexora-production-activation

Certified Activation Commit: 28c03e5e722b812351d77bdf357538f56b43d942

### Protected Baselines

- v1.1.0: f457f8afac89a1c196e9992a99e7b8b652182c7a

- Production GA: e5365c14aaae7dc4aac56bc34f435ae173bc6b2e

- Production Activation / Final Local Product Closure: 28c03e5e722b812351d77bdf357538f56b43d942

The v1.1.0 and Production GA baselines are immutable release authorities. They must not be rewritten, amended, retagged, force-updated, or changed merely to continue future development.

---

# 1. Purpose of This Handover

This document is the operating authority for the certified Nexora local-first product baseline.

It defines:

- what Nexora is;

- the certified architecture;

- the authoritative repository baseline;

- how the product should be configured and operated;

- how governed evidence moves through the platform;

- how Ask Nexora and Decision Intelligence operate;

- how Nexora should be demonstrated;

- how the first customer should be onboarded;

- which capabilities remain environment-specific;

- and how future product changes should be controlled.

This document does not reopen product development.

---

# 2. Product Purpose

Nexora is an Enterprise Technology Intelligence & Decision Platform.

It brings technology, financial, operational, governance, evidence, relationship, and decision information into a governed enterprise intelligence layer.

The intended product journey is:

Ask Understand Investigate Decide Approve Execute Measure

Nexora is intentionally local-first and cloud-portable.

The certified core product does not require AWS, Azure, or GCP merely to operate, demonstrate, or continue controlled development.

The product can later be hosted on:

- a local server;

- customer infrastructure;

- private cloud;

- GCP;

- Azure;

- AWS;

- or another compatible container platform.

Cloud hosting is a deployment decision rather than a dependency of the core application architecture.

---

# 3. Canonical Architecture

Source Systems / Connectors

&#x20;

LiveSource / SourceFacts

&#x20;

Enterprise Data Fabric

&#x20;

Enterprise Registry / Relationship Intelligence

&#x20;

Universal Evidence / Governed Workflows

&#x20;

Enterprise / Financial / Technology Intelligence

&#x20;

Ask Nexora

&#x20;

Recommendations / Decision Intelligence

&#x20;

Approval / Execution / Measurement

&#x20;

Executive & Persona Experiences

## Enterprise Data Fabric

The Enterprise Data Fabric is the canonical authority for:

- entity identity;

- enterprise relationships;

- lineage;

- provenance;

- data quality;

- versioning;

- semantic mappings;

- SourceFact authority.

A second competing Data Fabric must not be introduced.

## Universal Evidence

Universal Evidence provides governed evidence and workflow capabilities including:

- uploaded evidence;

- financial evidence;

- evidence lifecycle;

- governed evidence packages;

- evidence-backed AI workflows;

- evidence-backed decision workflows.

Universal Evidence complements the Enterprise Data Fabric. It does not replace it.

## SourceFacts

SourceFacts form the governed evidence boundary between source ingestion and downstream intelligence.

SourceFacts preserve:

- source identity;

- tenant and organization ownership;

- evidence references;

- provenance;

- quality metadata;

- lineage.

## Ask Nexora

Ask Nexora consumes governed context rather than unrestricted raw source data.

The AI contract requires:

- governed evidence;

- evidence and citation references;

- tenant and persona context;

- semantic plan validation;

- fail-closed behavior for unsupported plans;

- explicit UNKNOWN handling;

- no fabrication of unsupported values.

## Decision Intelligence

Decision Intelligence connects:

- recommendations;

- evidence;

- provenance;

- policy;

- approval;

- decision status;

- execution;

- outcome measurement.

The objective is not simply to recommend an action. It is to ensure that a decision remains traceable to governed evidence.

---

# 4. Certified Repository Baseline

Repository:

C:\\Users\\SrikanthMudaliar\\AI-Cloud-Advisor-p3-clean

Certified branch:

program/nexora-production-activation

Certified HEAD:

28c03e5e722b812351d77bdf357538f56b43d942

Protected authorities:

v1.1.0

f457f8afac89a1c196e9992a99e7b8b652182c7a

Production GA

e5365c14aaae7dc4aac56bc34f435ae173bc6b2e

Production Activation / Final Local Product Closure

28c03e5e722b812351d77bdf357538f56b43d942

Before any future development, verify:

git branch --show-current

git rev-parse HEAD

git status --short

Future development must occur through a new bounded branch rather than rewriting certified release history.

---

# 5. Certified Production Assets

The production baseline includes the following key authorities:

docker-compose.production.yml

.env.production.example

.env.production.backend.example

deploy/production/bootstrap-manifest.json

docs/production/PILOT_RUNBOOK.md

docs/production/PILOT_ACCEPTANCE_CHECKLIST.md

scripts/check_pilot_readiness.py

docs/production/NEXORA_FINAL_LOCAL_PRODUCT_CERTIFICATION.md

Primary runtime entry points include:

app_main.py

backend/main.py

backend/celery_app.py

docker-compose.production.yml

The production runtime is a portable deployment contract rather than a cloud-provider-specific architecture.

# 6. Production Configuration

The canonical production configuration templates are:

.env.production.example

.env.production.backend.example

Important runtime configuration includes:

ENVIRONMENT

JWT_SECRET

SUPABASE_URL

SUPABASE_KEY

NEXORA_UNIVERSAL_EVIDENCE_DB

DEFAULT_ORG_ID

NEXORA_DEMO_MODE

SCHEDULER_TZ

BACKGROUND_JOBS_ENABLED

OPENAI_API_KEY

OPENAI_MODEL

Privileged backend configuration can include service-role credentials.

Production configuration rules:

- ENVIRONMENT must reflect the target environment.

- Demo authentication or demo mode must not substitute for production authentication.

- Real secrets must never be committed to Git.

- Service-role credentials must remain backend-only.

- Customer connector credentials must use least privilege.

- Only connectors required by the deployment should be configured.

- External AI credentials are required only when external AI is deliberately enabled.

---

# 7. Production Readiness

The repository contains the certified pilot-readiness checker:

.\\.venv\\Scripts\\python.exe scripts\\check_pilot_readiness.py

The completed certification established repository-level production and pilot readiness.

Environment-dependent capabilities can legitimately remain ENVIRONMENT_REQUIRED until the corresponding integration is activated.

The following distinction must always be preserved:

Repository certified

does not mean

every external customer environment is already configured.

---

# 8. Production Runtime

The authoritative production container contract is:

docker-compose.production.yml

Before deployment, validate the production Compose configuration:

docker compose -f docker-compose.production.yml config

Operational startup and customer-environment deployment must follow:

docs/production/PILOT_RUNBOOK.md

Historical development Compose files must not silently replace the certified production contract.

Routine shutdown must preserve persistent evidence, database, and runtime volumes unless destructive cleanup has been deliberately approved.

Background processing must remain explicitly controlled.

Worker, beat, or scheduler capabilities must not be enabled merely because implementations exist. They should be activated only when their deployment requirements and scheduling ownership have been validated.

---

# 9. Health, Readiness and Metrics

The backend exposes operational health and metrics capabilities including:

/health

/metrics

Production operations should verify:

- frontend availability;

- API health;

- metrics availability;

- authentication availability;

- database availability;

- evidence persistence;

- enabled connector health.

Health endpoint success is not equivalent to a certified production SLA.

Capacity, load, availability, and SLA validation remain deployment-specific.

---

# 10. Authentication and Tenant Isolation

Nexora contains organization, tenant, role, permission, and authentication boundaries.

Production execution must preserve organization and tenant context throughout the governed chain:

Authentication

 API

 Data Fabric

 SourceFacts

 Intelligence

 Ask Nexora

 Decisions

Cross-tenant access must never be introduced as a workaround for configuration or authorization problems.

Live Supabase authentication remains an environment-specific activation requirement where that authentication model is used.

Frontend components must never receive privileged service-role credentials.

---

# 11. Database Bootstrap

The canonical bootstrap authority is:

deploy/production/bootstrap-manifest.json

Certified manifest SHA256:

4D9E0DE8EF1E19FE600605E8DC9FEA61C226442111E4A27F6F1724290EF190C0

The certified bootstrap order is:

1\. public bootstrap;

2\. dated public migrations;

3\. Enterprise Data Fabric migrations;

4\. Universal Evidence local SQLite lifecycle;

5\. SourceFact local SQLite authority;

6\. live connector local SQLite persistence.

This sequence must not be arbitrarily reordered.

The completed database certification proved:

- clean disposable PostgreSQL replay;

- required public schema behavior;

- Data Fabric schema behavior;

- Row Level Security controls;

- required database functions;

- required database policies;

- Universal Evidence local lifecycle;

- SourceFact local authority;

- connector local persistence lifecycle.

The bootstrap manifest remains a frozen certification authority. Historical status fields inside that manifest must not be rewritten simply because later certification phases completed additional validation.

---

# 12. Governed Evidence Path

The certified local-first evidence flow is:

File / Source

 Evidence Admission

 Universal Evidence

 SourceFact

 Governed Financial / Enterprise Intelligence

 Ask Nexora

 Decision Intelligence / Evidence Trace

Local upload is a valid evidence transport.

A future live connector changes the transport or source. It does not require replacement of the downstream governance architecture.

Evidence provenance must remain available throughout the downstream intelligence and decision path.

---

# 13. LiveSource and Connector Operating Model

Nexora contains connector architecture for cloud, observability, collaboration, ITSM, development, productivity, and enterprise sources.

The architecture distinguishes between:

1\. governed source publication into SourceFacts; and

2\. operational connector persistence used by connector-specific workflows.

These responsibilities must not be conflated.

A connector implementation being present in the repository does not mean a live customer integration has already been certified.

Current closure status:

AWS live activation = ENVIRONMENT_DEFERRED

Azure live activation = ENVIRONMENT_DEFERRED

GCP live activation = ENVIRONMENT_DEFERRED

This is intentional.

Cloud credentials or infrastructure are not required to demonstrate the certified local-first product.

---

# 14. Ask Nexora Operating Contract

The governed Ask Nexora path is:

Question

 Semantic Planning

 Plan Validation

 Governed Retrieval

 CopilotContext

 Evidence

 AI Provider

 Grounded Answer

 Evidence References / UNKNOWN

External OpenAI execution requires appropriate configuration including:

OPENAI_API_KEY

OPENAI_MODEL

The production behavior must preserve UNKNOWN whenever governed evidence does not support an answer.

Semantic validation and evidence guards must not be weakened simply to obtain a more fluent AI response.

The certified live AI validation demonstrated that Ask Nexora can use governed context while preserving UNKNOWN for unsupported values.

AI generation is therefore downstream of evidence governance rather than a replacement for it.

---

# 15. Decision Intelligence

The governed decision lifecycle is:

Recommendation

 Evidence

 Provenance

 Policy

 Approval

 Decision

 Execution

 Outcome / Measurement

Decision records must remain evidence-backed.

Pilot-001E certified:

- the Decision Intelligence runtime contract;

- recommendation and decision linkage;

- evidence traceability;

- provenance behavior;

- governed decision evidence paths.

This certification does not claim that every future customer decision workflow has already been executed against a live customer environment.

---

# 16. Executive and Persona Experience

Nexora contains executive and role-oriented experiences covering areas such as:

- executive leadership;

- finance;

- technology;

- architecture;

- FinOps;

- operations;

- administration;

- governance and security.

Not every Python page present in the repository should automatically be exposed to every user.

Canonical navigation, role controls, and persona design remain the authority for the supported product experience.

Historical, development, backup, experimental, or non-canonical pages must not be surfaced merely because files remain in the repository.

# 17. Golden Demo

The Golden Demo should demonstrate one coherent enterprise decision story rather than attempting to show every capability in the repository.

Recommended flow:

1\. Sign in.

2\. Establish organization and persona context.

3\. Open the executive experience.

4\. Show technology and financial posture.

5\. Ingest or select governed evidence.

6\. Show evidence-backed intelligence.

7\. Ask Nexora a business question.

8\. Show the grounded answer and UNKNOWN behavior where evidence is insufficient.

9\. Open the associated recommendation or Decision Intelligence workflow.

10\. Show evidence and provenance traceability.

11\. Show the approval and governance lifecycle.

12\. Return to the executive outcome.

The core demonstration story is:

Evidence

 Intelligence

 Ask

 Decision

 Governance

The Golden Demo should not become a tour of every repository page.

The objective is to demonstrate how Nexora converts governed enterprise evidence into explainable intelligence and traceable decisions.

---

# 18. First Customer Pilot

The first customer pilot should deliberately remain bounded.

Recommended initial footprint:

- 1 organization;

- 1 administrator;

- 25 users;

- 1 real source or governed file source;

- 1 cost dataset;

- 12 business services;

- a small technology inventory;

- owners and relationships;

- Ask Nexora;

- executive experience;

- 1 recommendation or decision workflow.

Recommended activation sequence:

Environment Preparation

 Organization Creation

 Authentication

 Users / Roles

 Source Activation

 Evidence Ingestion

 SourceFact Verification

 Data Fabric Verification

 Intelligence Verification

 Ask Nexora Validation

 Decision Trace Validation

 Customer Acceptance

The first pilot should prove:

- business value;

- usability;

- evidence governance;

- operational reliability;

- customer-specific integration requirements;

- decision traceability.

The integration footprint should expand only after these fundamentals are proven.

---

# 19. Environment-Deferred Capabilities

The following capabilities remain customer or deployment specific:

- live Supabase authentication;

- live customer connectors;

- external AI configuration;

- external notifications;

- external DNS and TLS;

- cloud hosting;

- production load validation;

- production SLA validation.

These are not unresolved core architecture defects.

They become required when the corresponding customer or deployment model requires them.

---

# 20. Cloud Deployment Policy

Cloud deployment remains intentionally deferred until there is a genuine external hosting requirement.

No AWS, Azure, or GCP account is required simply to continue demonstrating, maintaining, or validating the certified local-first core product.

When a customer requires externally accessible hosting, Nexora can be deployed to an appropriate target environment while preserving the cloud-neutral core architecture.

Core domain logic must not become dependent on a hosting provider merely to simplify one deployment.

The same certified product architecture should remain deployable across:

- local infrastructure;

- customer infrastructure;

- private cloud;

- AWS;

- Azure;

- GCP;

- compatible container environments.

---

# 21. Backup and Recovery

Operational references include:

docs/NEXORA_BACKUP_RECOVERY_GUIDE.md

docs/NEXORA_OPERATIONS_RUNBOOK.md

docs/production/PILOT_RUNBOOK.md

Before a real customer production deployment, establish and validate:

- database backup;

- evidence-store backup;

- configuration backup;

- secrets recovery procedure;

- restore procedure;

- retention requirements;

- recovery ownership;

- recovery testing.

A backup is not considered operationally sufficient until restore behavior has been validated for the target deployment.

---

# 22. Security Operating Rules

Never:

- commit production or customer secrets;

- print secrets into diagnostic output;

- expose service-role credentials to frontend components;

- disable tenant isolation to bypass authorization;

- bypass evidence governance for AI answers;

- use demo authentication as production authentication;

- enable unnecessary cloud credentials;

- force-push certified release history;

- move or recreate the certified v1.1.0 tag.

Customer connector credentials must follow least-privilege principles.

Production configuration should contain only the credentials and capabilities required by that deployment.

---

# 23. Troubleshooting Classification

Before changing application code, classify the issue.

Use one of the following classifications:

PRODUCT DEFECT

CONFIGURATION DEFECT

ENVIRONMENT REQUIRED

EXTERNAL SERVICE FAILURE

TEST / HARNESS DEFECT

Recommended troubleshooting order:

1\. Git baseline.

2\. Environment configuration.

3\. Runtime and container health.

4\. Authentication.

5\. Tenant and organization context.

6\. Database and bootstrap.

7\. Evidence ingestion.

8\. SourceFact publication.

9\. Data Fabric and governed capability.

10\. Ask Nexora context.

11\. AI provider.

12\. Decision and approval lifecycle.

13\. Connector-specific external environment.

Environment or credential failures must not automatically be treated as product defects.

Test-harness defects must not automatically trigger product remediation.

---

# 24. Change Control and Product Freeze

The completed program should not be followed by another speculative architecture phase.

Future development should be triggered by evidence such as:

- a pilot defect;

- a customer requirement;

- a security requirement;

- an operational requirement;

- a performance requirement;

- a required integration;

- a commercial requirement.

The future change flow should be:

Certified Baseline

 Bounded Branch

 Explicit Requirement and Scope

 Implementation

 Focused Validation

 Regression Where Warranted

 Acceptance

 Atomic Commit

 Controlled Publication

Certified release history must not be rewritten.

No new major capability should be introduced merely because it is technically possible.

---

# 25. Certification Summary

The completed Nexora program established:

- immutable v1.1.0 release;

- Production GA certification and publication;

- portable production runtime;

- production configuration boundaries;

- database bootstrap certification;

- external pilot readiness;

- SourceFact authority;

- governed local evidence ingestion;

- financial intelligence;

- Ask Nexora contract;

- controlled live grounded OpenAI execution;

- UNKNOWN preservation;

- Decision Intelligence;

- decision evidence traceability;

- local-first and cloud-portable architecture;

- final local product certification;

- remote publication of the production activation branch.

Pilot-001E is closed as PASS.

The certified local-first product path is:

Governed Evidence

 SourceFacts

 Financial / Enterprise Intelligence

 Ask Nexora

 Decision Intelligence

 Evidence / Provenance Trace

---

# 26. Certification Boundaries

The certification does not claim that:

- every connector is connected to a live customer;

- AWS customer credentials are configured;

- Azure customer credentials are configured;

- GCP customer credentials are configured;

- cloud production infrastructure has been created;

- production-scale load testing has been completed;

- a customer production SLA has been validated;

- all external notification channels are active;

- every repository page belongs to the canonical user experience.

These capabilities require the corresponding real customer or deployment environment.

---

# 27. Approved Production Claim

The approved production statement is:

Nexora Production GA is repository/code-contract/UAT/reliability certified and published. The local-first product path through governed evidence, SourceFacts, financial intelligence, Ask Nexora, Decision Intelligence and evidence/provenance traceability is certified. Live customer integrations, customer-specific cloud deployment and production load/SLA validation remain environment-specific activation activities.

This statement should be used instead of broader claims that imply every external customer integration or production environment has already been certified.

---

# 28. Final Product Status

CORE_LOCAL_FIRST_PRODUCT=READY

V1_1_0=CERTIFIED

PRODUCTION_GA=CERTIFIED_AND_PUBLISHED

PRODUCTION_ACTIVATION=CERTIFIED_AND_PUBLISHED

PILOT_001E=PASS

LOCAL_EVIDENCE_PATH=VERIFIED

SOURCEFACT_AUTHORITY=VERIFIED

FINANCIAL_INTELLIGENCE=VERIFIED

ASK_NEXORA_CONTRACT=VERIFIED

LIVE_OPENAI_GROUNDED_ASK=VERIFIED

UNKNOWN_PRESERVATION=VERIFIED

DECISION_INTELLIGENCE=VERIFIED

DECISION_EVIDENCE_TRACE=VERIFIED

LIVE_CUSTOMER_CONNECTORS=ENVIRONMENT_DEFERRED

CLOUD_DEPLOYMENT=ENVIRONMENT_DEFERRED

PRODUCTION_LOAD_SLA=ENVIRONMENT_SPECIFIC

SPECULATIVE_DEVELOPMENT_REQUIRED=NO

---

# 29. Final Handover Decision

The current Nexora construction, certification, and local production-activation program is complete.

Nexora should now move from architecture-driven construction to demo-, pilot-, and customer-driven operation.

The certified repository baseline should be preserved.

Future engineering work should be initiated only against a demonstrated requirement and performed through bounded, controlled change.

No further speculative platform-development phase is required.

The next operational milestone is:

GOLDEN DEMO

 FIRST CUSTOMER PILOT

 CUSTOMER-SPECIFIC ACTIVATION

 MEASURED PRODUCT EVOLUTION
