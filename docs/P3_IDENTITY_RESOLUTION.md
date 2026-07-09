# P3 Identity Resolution

P3.4 introduces identity resolution interfaces for canonical Enterprise Data Fabric entities. This is an interface and in-memory reference layer only.

## Scope

Included:

- `IdentityResolver` abstract interface.
- `InMemoryIdentityResolver` reference implementation.
- `MatchCandidate`, `MatchResult`, and `MatchDecision` matching primitives.
- Deterministic confidence scoring for exact and heuristic matches.
- Explicit duplicate and no-match outcomes.

Excluded:

- Database persistence.
- Supabase writes.
- Migrations.
- Dashboard changes.
- Connector runtime changes.
- Knowledge Graph writes or graph projection.
- P1/P2 behavior changes.

## Matching Signals

The in-memory resolver supports these signals in priority order:

| Signal | Confidence | Reason |
| --- | ---: | --- |
| Exact `canonical_id` | `1.00` | `canonical_id` |
| Exact `source_system` + `source_identifier` | `0.98` | `source_identity` |
| Normalized entity name | `0.86` | `normalized_name` |
| Candidate/entity alias match | `0.80` to `0.82` | alias-specific reason |

Matches are scoped by `organization_id`. Candidates from a different organization do not match even when other fields align.

## Outcomes

- `MATCH`: one best canonical entity was found.
- `DUPLICATE`: multiple canonical entities matched explicitly or above the duplicate threshold.
- `NO_MATCH`: no candidate met a supported matching signal.

## Persistence Position

The in-memory resolver stores entities only inside the Python object instance. It does not write to Supabase, local databases, files, dashboards, connector runtimes, or graph stores.
