# ADR-015: Data Quality Framework

Status: Accepted — P3 foundation implemented and validated
Date: 2026-07-09
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

Enterprise intelligence is only useful when users understand the quality of the data behind it. Completeness, freshness, accuracy, consistency, validity, ownership, and verification status must be visible across the platform.

## Decision

Introduce a Data Quality Framework for canonical entities, relationships, data products, dashboards, and AI recommendations.

Each entity should expose:

- Completeness
- Freshness
- Accuracy
- Consistency
- Validity
- Trust score
- Owner
- Last verified

## Rules

- Quality scores must be explainable.
- Quality dimensions remain separate before being combined into trust score.
- Quality degradation should be visible to dashboards and AI services.
- Data quality ownership is part of the entity contract.

## Consequences

Users can distinguish high-confidence intelligence from incomplete, stale, or disputed signals. AI outputs can adapt confidence and language based on quality posture.
