# ADR-010: Enterprise Semantic Layer

Status: Proposed
Date: 2026-07-09
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

Different providers use different terms for equivalent capabilities. AWS EC2, Azure VM, and GCP Compute Engine should be understood as Virtual Machine. AWS S3, Azure Blob, and GCS should be understood as Object Storage.

## Decision

Create an Enterprise Semantic Layer that maps source-specific concepts to provider-neutral enterprise concepts.

The semantic layer will define:

- Enterprise object types
- Synonyms and aliases
- Provider mappings
- Capability groups
- Taxonomy hierarchy
- Semantic confidence
- Versioned ontology references

## Rules

- Provider mappings are versioned and reviewable.
- Semantic normalization is explainable and reversible.
- AI and analytics consume semantic concepts instead of source-specific labels.
- Ambiguous mappings carry confidence and evidence, not silent certainty.

## Consequences

Cross-provider analytics, rationalization, recommendations, and AI reasoning can operate on enterprise concepts while preserving the original provider evidence.
