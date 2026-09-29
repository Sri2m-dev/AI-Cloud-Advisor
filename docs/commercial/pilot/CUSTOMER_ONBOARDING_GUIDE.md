# Nexora Customer Onboarding Guide

## Commercial Journey

**Upload -> Prove -> Connect -> Automate**

Customers can begin without direct cloud access and progress toward connected intelligence when appropriate.

## Option A - Zero-Access Evidence Import

Use this mode when direct cloud access is unavailable or not yet approved.

Customer steps:

1. agree pilot scope;
2. identify approved evidence;
3. export the evidence;
4. remove unnecessary sensitive information;
5. provide it through the agreed transfer process;
6. validate Nexora findings.

Nexora processes approved evidence through:

Evidence Admission
-> Universal Evidence
-> SourceFacts
-> Data Fabric
-> Enterprise Intelligence
-> Ask Nexora
-> Decision Intelligence

## Option B - AWS Connected Mode

Use this mode when continuous or repeatable AWS discovery is required and customer security approval exists.

Customer steps:

1. receive the Nexora AWS principal information;
2. receive the Nexora-generated External ID;
3. create a customer-side read-only IAM role;
4. configure the required trust relationship;
5. attach the agreed read-only permissions;
6. provide the Role ARN;
7. participate in connection and scope validation.

Nexora uses STS AssumeRole and temporary credentials.

Customer long-lived AWS access keys are not required.

## Security Principles

- least privilege;
- read-only discovery;
- tenant and organization isolation;
- temporary AWS credentials;
- governed evidence;
- provenance preservation;
- UNKNOWN for unsupported conclusions.

## Connected Mode Does Not Automatically Authorize

- creation of customer resources;
- workload modification;
- service enablement;
- infrastructure remediation;
- bypass of customer change control.

## Pilot Experience

The curated customer journey is:

**Analyze Environment**
-> **Executive Experience**
-> **Decision Intelligence**
-> **Ask Nexora**
-> **Reports / Outcome Review**

Not every repository page should be exposed merely because it exists.

## Environment-Specific Requirements

Depending on deployment model, activation may still be required for:

- live Supabase authentication;
- Nexora AWS principal;
- customer IAM Role ARN;
- live STS validation;
- DNS/TLS;
- external AI provider where deliberately enabled;
- notification integrations where enabled;
- production infrastructure.
