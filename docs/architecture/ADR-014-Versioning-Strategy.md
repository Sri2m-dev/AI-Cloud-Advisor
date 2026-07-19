# ADR-014: Versioning Strategy

Status: Accepted — P3 foundation implemented and validated
Date: 2026-07-09
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

Enterprise entities, relationships, semantic mappings, quality rules, and AI explanations will change over time. Without versioning, historical dashboards and decisions become impossible to explain.

## Decision

Adopt versioning for canonical entities, relationships, ontology mappings, quality rules, and derived intelligence.

Versioned objects must support:

- Current state
- Historical state
- Effective timestamp
- Source update timestamp
- Transformation version
- Change reason
- Superseded-by reference

## Rules

- Canonical ID remains stable across versions.
- Version increments when business meaning changes.
- Low-level source refreshes do not create new semantic versions unless canonical meaning changes.
- AI recommendations reference the versions they used.

## Consequences

Nexora can explain historical decisions, compare estate changes over time, and avoid mixing stale reasoning with current-state dashboards.
