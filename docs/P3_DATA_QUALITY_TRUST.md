# P3 Data Quality and Trust Scoring Interfaces

P3.6 introduces provider-agnostic data-quality assessment and trust scoring for canonical entities and relationships. The implementation is deterministic and in-memory only.

## Architecture

The package is isolated under `data_fabric/quality`:

- `DataQualityEvaluator` assesses canonical contracts.
- `TrustScoreCalculator` defines score calculation behavior.
- `QualityRule` is the injectable extension point for later provider or domain rules.
- `InMemoryDataQualityEvaluator` runs default rules and custom rules without persistence.
- `WeightedTrustScoreCalculator` calculates final 0-100 trust scores from dimension scores.

The evaluator reuses models from `data_fabric/contracts` and can accept optional lineage or provenance evidence from `data_fabric/lineage`. It is not wired into registries, identity resolution, dashboards, connectors, databases, or graph projection.

## Dimensions

Default dimensions are:

- `completeness`
- `freshness`
- `validity`
- `consistency`
- `uniqueness`
- `accuracy`
- `lineage_confidence`
- `source_confidence`
- `ownership_completeness`

Scores use a consistent 0-100 scale. Invalid score inputs are rejected explicitly.

## Default Weights

| Dimension | Weight |
| --- | ---: |
| completeness | 0.18 |
| freshness | 0.10 |
| validity | 0.14 |
| consistency | 0.10 |
| uniqueness | 0.08 |
| accuracy | 0.12 |
| lineage_confidence | 0.10 |
| source_confidence | 0.10 |
| ownership_completeness | 0.08 |

Weights must include every default dimension, cannot be negative, and must total `1.0`.

## Severity Levels

- `warning`: non-blocking issue that reduces a dimension score.
- `blocking`: validation failure that should block promotion or automated use until resolved.

Blocking issues and warnings are both retained in `QualityAssessment.issues` and can be queried separately.

## Score Calculation

Each rule returns a `QualityRuleResult` for one dimension. When multiple rules evaluate the same dimension, the evaluator uses the lowest score so severe failures cannot be hidden by passing rules. Missing dimensions are explicitly scored as `0` with a warning; they never receive a silent perfect score.

The trust score is the weighted sum of dimension scores. Explanations include each dimension score, weight, deduction, and final score.

## Extension Model

Provider-specific or domain-specific rules must be injected through `register_rule`. The core package does not contain AWS, Azure, GCP, SaaS, ITSM, dashboard, or product-specific interpretations.

## Tenant Isolation

Assessments preserve `organization_id` and `tenant_id`. Batch evaluation keys include organization context so objects with the same source id in different organizations are not combined.

## Examples

```python
from data_fabric.quality import InMemoryDataQualityEvaluator

evaluator = InMemoryDataQualityEvaluator()
assessment = evaluator.evaluate_entity(entity, uniqueness_confirmed=True)
print(assessment.trust_score.final_score)
print(evaluator.explain_score(assessment))
```

## Current Limitations

- No persistence is included.
- No Supabase/database writes are included.
- No migrations are included.
- No dashboard, connector runtime, registry, identity resolver, or graph integration is included.
- Freshness is currently timestamp-availability based; age policies can be injected later as custom rules.
