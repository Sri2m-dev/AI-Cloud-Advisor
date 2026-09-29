# Nexora First Customer Pilot

## Purpose

The Nexora First Customer Pilot demonstrates how governed customer technology evidence can be converted into enterprise, financial, technology and decision intelligence.

The commercial progression is:

**Upload -> Prove -> Connect -> Automate**

The pilot may begin with Zero-Access Evidence Import and later progress to AWS Connected Mode without changing Nexora's canonical intelligence architecture.

## Pilot Objective

The pilot should demonstrate that Nexora can:

- onboard approved customer evidence;
- preserve customer, tenant and organization boundaries;
- normalize supported evidence into governed SourceFacts;
- use the existing Data Fabric, Registry and relationship model;
- produce evidence-backed enterprise, financial and technology intelligence;
- answer customer questions through Ask Nexora;
- preserve provenance and evidence coverage;
- return UNKNOWN when evidence does not support a conclusion;
- connect findings to a recommendation or decision workflow.

## Initial Pilot Footprint

The first customer pilot should remain bounded:

- one customer organization;
- a small technology inventory;
- relevant owners and relationships;
- financial/cost evidence where approved;
- Ask Nexora;
- executive experience;
- one recommendation or decision workflow.

## Supported Onboarding Modes

### Zero-Access Evidence Import

Customer-approved evidence
-> Governed Admission
-> Semantic Governance
-> Normalization
-> SourceFacts
-> Data Fabric / Registry / Relationships
-> Enterprise / Financial / Technology Intelligence
-> Ask Nexora

This mode does not require direct Nexora access to the customer's cloud account.

### AWS Connected Mode

Customer AWS
-> Customer-created read-only IAM role
-> Nexora AWS Principal
-> STS AssumeRole with Nexora-generated External ID
-> Temporary credentials
-> Controlled discovery and synchronization
-> SourceFacts
-> Data Fabric / Registry / Relationships
-> Enterprise / Financial / Technology Intelligence
-> Ask Nexora

Customer long-lived AWS access keys are not required.

## Customer Journey

1. Establish organization, users and persona.
2. Select the approved onboarding mode.
3. Activate the source or upload governed evidence.
4. Verify evidence admission and SourceFacts.
5. Review evidence coverage and provenance.
6. Review technology and financial posture.
7. Open the Executive Experience.
8. Ask Nexora customer-specific questions.
9. Review the grounded answer and UNKNOWN behavior.
10. Review one recommendation or Decision Intelligence workflow.
11. Trace the decision back to evidence.
12. Complete customer acceptance.

## Pilot Outcomes

The pilot should establish:

- demonstrated business value;
- usability;
- evidence governance;
- operational reliability;
- customer-specific integration requirements;
- evidence/data gaps;
- confirmed product defects, if any;
- validated product gaps, if any;
- appropriate next commercial step.

## Certification Boundary

Repository and local application-runtime certification are separate from customer-environment certification.

Environment-specific activities can include:

- live Supabase authentication;
- deployed Nexora AWS principal;
- customer IAM Role ARN;
- live STS AssumeRole;
- customer-specific AWS permissions;
- live resource/cost synchronization;
- DNS/TLS;
- external notifications where enabled;
- production infrastructure;
- production load/SLA validation.

These must not be represented as already live-certified.

## Product Principle

The pilot validates Nexora against real customer evidence.

It is not a vehicle for speculative feature development.
