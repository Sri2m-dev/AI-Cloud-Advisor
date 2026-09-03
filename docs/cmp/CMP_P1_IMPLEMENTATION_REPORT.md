# CMP-P1 Implementation Checkpoint

## Status

CMP-P1G is complete and CMP-P1 now meets every final exit criterion. Recommended final
status: **PASS**. Synthetic, external production, restart, security, and repository
regression certification are green.

## P1.1 spreadsheet tooling

**OPENPYXL FALLBACK — EXPLICITLY AUTHORIZED**

- Reason: the spreadsheet artifact runtime was unavailable in the execution environment.
- Scope: creation and verification of the five independent synthetic acceptance workbooks.
- Impact on production architecture: **NONE**.
- Dependency: reused the repository's existing pinned `openpyxl` dependency.
- Determinism: acceptance uses canonical workbook structure, cell content, row counts,
  totals, breakdowns, currencies, and governance outcomes rather than unstable XLSX ZIP
  metadata hashes.
- Separation: production code does not import the fixture generator or ground-truth
  manifest.

The generated fixtures contain fictional `ExampleCo-Test`, `svc-fictional-*`,
`app-fictional-*`, and `resource-test-*` identifiers. They were generated independently
and contain no copied client values or identifiers.

## Implemented work packages

- P1.2–P1.3: domain/provider classification and multi-signal semantic proposals.
- P1.4–P1.8: financial concepts, relationships, governed currency, additive-measure
  authorization, and cost classification.
- P1.9–P1.11: provenance-complete canonical observations, tenant-scoped durable
  publication, and Enterprise Spend service/region consumption.
- P1.12–P1.14: explicit confirmation requirements, restart/purge/idempotency,
  cross-tenant isolation, kill-switch enforcement, and fail-closed behavior.
- P1.15: all five synthetic acceptance fixtures pass through the production admission and
  financial-intelligence boundary.
- P1.16: executed against the two local confidential CUR workbooks without modifying or
  committing them; governed service-level publication and production consumption passed,
  but the end-user confirmation journey remains incomplete.

## External real-CUR result

- Workbook 1: cached formula values were admitted with provenance, the numeric unit-rate
  candidate was ranked correctly, and the additive amount reconciled for all 184 detail
  rows. It published 184 observations with supported service and region breakdowns.
- Workbook 2: leading workbook context plus a provider-neutral temporal financial matrix
  produced governed domain and measure proposals. Currency remained correctly UNKNOWN
  until explicit human confirmation. After confirmation, 44 detail observations published;
  all 11 period summaries reconciled within 0.1%, and the summary row was excluded.

No client-specific headers, values, filenames, hashes, row counts, or parsing rules were
added. Unsupported CUR 2 region evidence remains UNKNOWN as required.

The production Analyze Environment experience now persists domain, semantic-measure, and
currency authority through the scoped Universal Evidence lifecycle store. Publication binds
decision IDs and versions into observation fingerprints. Rejection purges stale publication;
override preserves immutable history and creates new authority.

## Certification evidence

- CMP-P1/P1R/P1G focused tests: 22 passed.
- Universal Evidence: 601 passed.
- ACT-009–013: 163 passed.
- Prospect: 35 passed.
- Data Fabric: 309 passed.
- Registry/KG: 154 passed.
- Cost Intelligence: 85 passed.
- Executive/context: 147 passed.
- Ask Nexora: 73 passed.
- Full repository: 1,725 passed, 2 skipped.
- Active-source compile: passed.
- Scoped Ruff: passed.
- Current-tree secret scan: passed.
- Tracked runtime-artifact scan: passed.
- Git whitespace checks: passed.

## Remaining gates

1. REL-C1 remains independently blocked on external credential rotation/revocation and
   database access-log review.
2. REL-002 has not begun.

## CMP-P1G closure

- High-confidence domain and additive-measure policy decisions persist as scoped authority.
- Unknown currency remains blocked until an authorized product user confirms it.
- Currency rejection blocks aggregation and removes stale current publication.
- Currency override supersedes the prior decision while retaining immutable history.
- Domain or semantic-measure rejection blocks publication.
- Same evidence and authority are idempotent; authority changes produce versioned
  publication fingerprints.
- Encrypted workspace resume reconstructs evidence, decisions, publication, and Enterprise
  Spend without re-upload or reconfirmation.
- Cross-analysis, cross-prospect, cross-tenant, purged, and stale evidence authority fail
  closed.
- External CUR 1 reconstructed 184 observations and the same spend after restart.
- External CUR 2 reconstructed 44 observations after one production currency confirmation
  and returned the same spend after restart.
