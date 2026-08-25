# PUE-002 Semantic Column Discovery

## Status and authority

PUE-002 produces deterministic hypotheses about column meaning from immutable PUE-001
`FileProfile` objects. Results remain in-memory, shadow-mode, non-authoritative candidates. The
classifier performs no raw-source access, parsing, value normalization, persistence, aggregation,
entity creation, relationship creation, query-capability evaluation, UI integration, or Ask Nexora
integration.

`AUTO_CLASSIFIED` means only that an interpretation is strong enough to be automatically proposed.
It never means normalized, confirmed, queryable, or canonical.

## Input and output boundary

Inputs are limited to original headers, primitive profiles, structural roles, coverage,
cardinality, bounded safe samples and their row references, sheet-local headers/names, structural
warnings, and analysis/source/file/sheet/column provenance. Filenames are retained in the PUE-001
file object but are not classification signals.

Every profiled column produces a `ColumnDiscoveryResult` containing zero or more candidates,
classification and confirmation-requirement states, bounded explanations, classifier/ontology/policy
versions, a deterministic ID, and structural provenance. `FileDiscoveryResult` provides only a
non-governed count of candidate dimensions and unclassified columns.

PUE-002 may emit `UNCLASSIFIED`, `CANDIDATE`, `AUTO_CLASSIFIED`, or
`CONFIRMATION_REQUIRED`. It cannot emit `USER_CONFIRMED`, `REJECTED`, or `OVERRIDDEN` and creates no
human confirmation record.

## Versioned concept registry

The in-memory registry version is `pue-ontology-1`. Each definition wraps the PUE-000
`SemanticConcept` contract with expected structural roles, risk, bounded context tokens, and an
optional safe-sample shape. Concept IDs remain versioned and aliases remain separate from ontology
identity.

Initial registry families include:

- Financial cost (total/monthly/unit), currency, price, savings, and budget
- Cloud provider, account, subscription, project, region, and availability zone
- Technology service, product, platform, and database
- Resource identifier, name, and type
- Organization business unit, department, and cost center
- Ownership owner, team, manager, and support group
- Application name, workload, and system
- Business service and capability
- SaaS vendor, license count, utilization, and subscription
- Contract identifier, start/end date, and renewal date
- Operational CPU, memory, utilization, and incident count
- Security severity, compliance, and control status
- Geography country, location, and region
- Tagging environment, project, and owner

Aliases and bounded abbreviations are declared in
`universal_evidence/semantic/concepts.py`. Examples include `spend`, `acct`, `dept`, `cc`, `qty`,
`util`, and `renewal dt`. There is no customer-specific or vendor-template alias store.

## Header normalization

Matching lowercases, trims, separates camelCase, replaces punctuation/separators, collapses
whitespace, and tokenizes. Original headers remain unchanged in PUE-001 and semantic provenance.
Exact aliases score strongest. An alias contained within a longer header is strong but not exact;
a generic short header contained within a longer alias receives only weak support. This prevents
`Cost` from being treated as `cost center` merely by token overlap.

## Signal and scoring model

The transparent score is:

```text
header alias                         0.60
primitive compatibility             0.15
structural-role compatibility       0.12
safe-sample shape                    0.05
sheet-local context                  0.08
primitive contradiction penalty    -0.35
```

Positive weights sum to 1.0 and are configurable through `DiscoveryConfig`. Every applied signal
becomes a `SemanticSignal` with type, safe explanation, and contribution. Sample explanations never
include sample values.

The first pass evaluates each column against the indexed versioned registry. The second, local
context signal considers neighboring original headers and the sheet name weakly. It never creates
row relationships, uses another file, or enforces a template. A sheet/file name cannot independently
create a candidate.

Primitive or role compatibility supports but does not prove meaning. A numeric `Renewal Date` or a
categorical text `Cost` receives a contradiction penalty. Safe sample shapes are limited to explicit
bounded forms such as three-letter currency codes, provider labels, and environment labels; sample
content alone cannot meet the candidate threshold without header evidence.

## Confidence model

Scores are clamped to 0.0–1.0. Default bands are:

| Band | Score |
| --- | --- |
| HIGH | >= 0.90 |
| MEDIUM | >= 0.70 and < 0.90 |
| LOW | >= 0.40 and < 0.70 |
| INSUFFICIENT | < 0.40 |

The minimum candidate score is 0.40 and the default automatic-proposal threshold is 0.90. These are
versioned policy defaults, not irreversible ontology facts.

## Ambiguity and confirmation policy

Confidence and confirmation remain independent. Confirmation is required when any of these apply:

- Concept risk is `HIGH_RISK` or `RESTRICTED`
- The top-two gap is below 0.12
- The top candidate contains a structural contradiction
- Column coverage is below 0.50
- Top confidence is below 0.90

A single candidate below the medium band remains `CANDIDATE`; other unresolved cases are
`CONFIRMATION_REQUIRED`. No candidate meeting the minimum produces `UNCLASSIFIED`, which is a valid
successful result. Policy reasons are explicit.

## Semantic risk

Concept metadata supports `LOW_RISK`, `MODERATE_RISK`, `HIGH_RISK`, and `RESTRICTED`. Financial
measures, ownership/organization identity, contracts, and similar authority-sensitive mappings are
high risk. Security compliance/control concepts are restricted. Environment labels are low risk.
The risk list that requires confirmation is configurable without changing the underlying score.

## Explanation and provenance

Each candidate records supporting and contradicting signals, concept/version, confidence method,
classifier version, threshold policy, risk, and confirmation requirement. Provenance contains:

- Analysis and source IDs
- File, sheet, and column IDs
- PUE-001 structural fingerprint and profiler version
- Safe-sample row references, never reopened raw values
- Classifier, ontology, and policy versions

The classifier version is `pue-002.1`; policy version is `pue-semantic-policy-1`.

## Determinism and performance

Rules, registry order, score sorting, IDs, and semantic fingerprints are deterministic. Fingerprints
bind the PUE-001 structural fingerprint to classifier, ontology, policy, configuration, and results.
No LLM, embedding, web request, stochastic process, cross-tenant cache, or learned customer memory is
used. Alias and concept data are held in-memory; representative tests cover up to 500 columns.

## Hard boundaries

- `EC2 Cost` may yield financial cost candidates but never AWS/EC2 value semantics.
- `i-0123456789abcdef` never creates an EC2 entity or provider claim.
- `Application Owner` may yield application/ownership candidates but no relationship.
- `aws_cur_january.csv` cannot create provider semantics from its filename.
- `technology.service` is a column hypothesis; values such as EC2/RDS/S3 remain untouched strings.
- Candidate presence never enables totals, currency resolution, query support, or AI answers.

## Privacy and security

Only PUE-001 samples are available. Suppressed samples remain absent and cannot be bypassed.
Candidate explanations and logs contain no customer values. There is no external semantic API,
telemetry, database, migration, scratch dump, or persistence.

## Known limitations

- The initial ontology and aliases are intentionally bounded and English-centric.
- Token overlap does not understand arbitrary customer abbreviations or language variants.
- Sheet-local context is weak and does not resolve cross-sheet or cross-file meaning.
- Sample-shape rules cover only a few explicit safe forms and do not normalize values.
- Risk assignments and thresholds require PUE-C2 governance review before broader use.
- Candidate dimension counts are discovery summaries, not governed evidence coverage.
- No user confirmation, override, rejection, audit, or mapping lifecycle exists in PUE-002.

## Certification and next boundary

PUE-C2 should certify determinism, candidate quality, contradiction behavior, ambiguity, risk,
privacy, provenance, and non-authority. PUE-003 may begin only after approval and should govern
confirmation decisions; it must not be implemented opportunistically here. Governed normalization
remains PUE-004.
