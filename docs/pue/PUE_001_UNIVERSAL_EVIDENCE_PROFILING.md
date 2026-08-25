# PUE-001 Universal Evidence Profiling

## Status and authority

PUE-001 implements structural observation in observational shadow mode. It does not integrate with
Streamlit, sessions, prospect analysis, Ask Nexora, currency resolution, canonical persistence, or
the Data Fabric. The existing prospect pipeline remains authoritative, and profiler failure cannot
invalidate an accepted upload.

The public boundary accepts an authorized `EvidenceSource`, original filename, immutable bytes, and
bounded `ProfilerConfig`. It never searches for paths, changes source bytes, persists results, or
transmits evidence externally.

## Supported inputs

- CSV through the Python standard library
- XLSX through the repository's existing pinned `openpyxl` dependency

Every workbook sheet is represented independently. A workbook is never treated as one universal
table. Unsupported formats and unsafe or malformed structures return explicit statuses rather than
fabricated schemas.

## Result model

`FileProfile` contains source/file identity, content hash, container format, size, profiler version,
profile time inherited from source receipt, file observations, and independent `SheetProfile`
objects. Each sheet contains its original name, visibility, observed region, candidate header,
structural confidence/method, original columns, primitive profiles, duplicate-row count, and
machine-readable warnings.

Profiles use these statuses:

- `COMPLETE`
- `PARTIAL`
- `UNSUPPORTED_FORMAT`
- `UNSUPPORTED_STRUCTURE`
- `MALFORMED`
- `FAILED`

`PARTIAL` is a successful truthful result. It is used when limits, irregular regions, malformed
recovery, or uncertain structure prevent a complete profile.

## CSV algorithm

1. Decode deterministically as UTF-8 with BOM support, UTF-16 when a BOM exists, or a documented
   cp1252 fallback.
2. Detect one of comma, semicolon, tab, or pipe delimiters with `csv.Sniffer`; use comma with a
   warning when detection is inconclusive.
3. Parse strictly first. If quoting is malformed, attempt bounded non-strict recovery and mark the
   result partial. No customer values enter diagnostics.
4. Score a header candidate using only density, uniqueness, primitive contrast, following-row
   support, and position. Business vocabulary is never consulted.
5. Preserve headers exactly, including blanks and duplicates.
6. Profile bounded logical data rows in one column-building pass.

Physical records and logical data rows are reported separately. Blank rows, inconsistent widths,
repeated header-like rows, separated regions, duplicate headers, and exact duplicate rows are
structural observations only.

## XLSX algorithm

The profiler checks expanded container size before opening a workbook. Each sheet is inspected for:

- Original name and visible/hidden state
- Used/observed range and independent candidate header row
- Empty leading and trailing physical rows
- Merged-cell regions
- Formula cells without formula execution
- Duplicate and unnamed headers
- Separated non-empty regions
- Primitive and structural column profiles

Formula expressions are observed as `FORMULA`. PUE-001 does not execute formulas or silently treat a
formula as equivalent to a cached value. `openpyxl` does not expose a reliable expression/cached-value
pair in one load, so cached-value authority remains an explicit later governance question.

Sheets with title rows, blank regions, mixed types, formulas, hidden status, or empty content retain
independent profiles. Multiple separated row regions produce `PARTIAL` with
`MULTIPLE_TABLE_REGIONS`; they are not merged.

## Primitive model

PUE-001 observes `NULL`, `BOOLEAN`, `INTEGER`, `DECIMAL`, `STRING`, `DATE`, `DATETIME`, `TIME`,
`FORMULA`, and `UNKNOWN`. ISO-shaped date/time strings and native spreadsheet temporal values may be
recognized structurally. A currency symbol remains lexical string structure and creates no currency
or financial meaning.

Column profiles report observed/null/non-null counts, coverage, distinctness, uniqueness, type
distribution, dominant primitive, mixed-type state, safe extrema, string lengths, structural roles,
bounded samples, and warnings. No sums or business aggregations are produced.

## Structural roles

Roles are reproducible shape observations, not semantic concepts:

- `IDENTIFIER_LIKE`: at least three values, high uniqueness, stable string/integer representation
- `MEASURE_LIKE`: dominant numeric values with variation
- `DATE_LIKE`: dominant date/time primitive
- `CATEGORICAL_LIKE`: stable repeated values with bounded cardinality
- `FREE_TEXT_LIKE`: long string observations
- `BOOLEAN_LIKE`: dominant boolean values
- `HIGH_CARDINALITY` / `LOW_CARDINALITY`
- `MOSTLY_NULL`
- `CONSTANT_VALUE`

Default thresholds are configurable: high cardinality 0.90, low cardinality 0.20, and mostly-null
coverage below 0.50. `IDENTIFIER_LIKE` never means `resource.identifier`; `MEASURE_LIKE` never means
cost, CPU, licenses, or another business measure.

## Sampling and privacy

Sampling takes the first distinct structurally safe values in row order, making the result
deterministic. The default is three samples and the PUE-000 contract caps configuration at five.
Samples retain row provenance. Long strings are truncated; very long, binary, control-character,
and high-entropy token-like values are suppressed. Suppression is conservative structural safety,
not PII classification. Values are not logged or persisted independently.

## Resource policy

Defaults align with, but do not change, accepted prospect limits:

- File: 25 MiB
- Expanded XLSX: 100 MiB
- Sheets: 50
- Logical rows: 500,000
- Columns: 2,000
- Samples per column: 3
- Sample length: 80 characters
- Header scan: 12 rows

Reaching a limit produces a partial result and `RESOURCE_LIMIT_REACHED`. The profiler uses bounded
input and avoids repeated full column scans; it does not claim full coverage beyond the observed
scope.

## Warning taxonomy

Warnings include `DUPLICATE_HEADERS`, `UNNAMED_COLUMNS`, `MIXED_PRIMITIVE_TYPES`, `EMPTY_SHEET`,
`HIDDEN_SHEET`, `MERGED_CELLS`, `FORMULAS_PRESENT`, `INCONSISTENT_ROW_WIDTH`,
`REPEATED_HEADER_ROWS`, `MULTIPLE_TABLE_REGIONS`, `LOW_DATA_DENSITY`,
`UNSUPPORTED_CELL_TYPE`, `SAMPLE_SUPPRESSED`, `MALFORMED_RECORDS`,
`RESOURCE_LIMIT_REACHED`, `HEADER_UNCERTAIN`, and `ENCODING_FALLBACK`. Details are safe and contain
no raw customer record dumps.

## Provenance and determinism

The chain is analysis/source → file → sheet/table → column → sample row. File identity derives from
the authorized source and SHA-256 content hash. Identical bytes, source identity, version, and
configuration produce the same `structural_fingerprint`; the fingerprint intentionally excludes
operational timestamps.

## Semantic boundary

PUE-001 never imports or emits semantic concept assignments. Filenames such as
`aws_cur_january.csv`, headers such as `AWS Service`, `EC2 Cost`, or `Application Owner`, and values
such as `i-0123456789abcdef` influence only factual primitive/cardinality observations. There is no
provider, service, cost, owner, application, currency, entity, recommendation, normalization, or AI
classification.

## Known limitations

- Header scoring intentionally prefers UNKNOWN/partial over vocabulary-based disambiguation.
- Separated regions are reported but not individually materialized as multiple candidate tables.
- CSV encoding detection is bounded and deterministic, not a probabilistic encoding classifier.
- CSV physical record count reflects parsed records, not raw newline count inside quoted fields.
- XLSX formulas are not evaluated and cached results are not asserted as equivalent evidence.
- Formatting-only cells may influence an XLSX library's reported used range; limits contain impact.
- Sample suppression is not comprehensive PII, secret, or compliance classification.
- Exact duplicate rows are structural byte/value equivalence, not entity deduplication.

## Certification boundary

PUE-001 can advance to PUE-C1 review after structural accuracy, privacy, resource containment,
determinism, provenance, and prospect regressions pass. PUE-002 remains unauthorized until explicit
approval and must introduce semantic discovery behind the Layer 1/Layer 2 boundary.
