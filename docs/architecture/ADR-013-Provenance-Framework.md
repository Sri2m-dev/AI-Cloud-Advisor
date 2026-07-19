# ADR-013: Provenance Framework

Status: Accepted — P3 foundation implemented and validated
Date: 2026-07-09
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

Lineage describes movement. Provenance describes authority, trust, transformation, and evidence. Nexora needs both to support executive-grade intelligence.

## Decision

Create a provenance framework for canonical entities, relationships, semantic mappings, quality scores, and AI outputs.

Provenance must capture:

- Source system
- Collection method
- Connector version
- Transformation version
- Normalization rule
- Identity resolution decision
- Confidence
- Quality posture
- Human override, when present
- Review timestamp

## Rules

- Derived facts must retain source evidence.
- Manual edits never erase source evidence.
- Conflicts are represented explicitly.
- Provenance is queryable by downstream services.

## Consequences

Trust signals become first-class platform data. Audit, governance, AI, and executive narratives can cite why a fact is trusted, disputed, stale, or inferred.
