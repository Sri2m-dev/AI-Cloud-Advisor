# PVT-003B — AWS CUR Ingestion Engine

Status: engineering complete; ready for review. No real CUR is loaded by this
increment.

## Boundary

`AwsCurIngestionEngine` is a backend-only orchestration service over the
certified PVT-003A tables. It requires `TenantContext` and a service-role
`CurPersistence` implementation. It has no Streamlit, REST, GraphQL, mart, or
dashboard integration; PVT-003C owns propagation.

## Parser profile

The `aws-cur-v1` profile accepts `.csv` and `.csv.gz`, including UTF-8 BOM.
One explicit alias table maps slash-form AWS headers and the observed
underscore-normalized export headers to internal semantic names before profile
validation. Ambiguous aliases fail closed. Downstream processing uses only the
internal names, while the complete original source row remains in `raw_fields`.
The engine derives the billing window in UTC from CUR billing timestamps and
rejects unsupported formats, missing fields, invalid timestamps, empty payers,
and mixed-payer files.

The parser streams with `csv.DictReader` in deterministic 10,000-row chunks
(bounded to 10,000–25,000). File hashing reads 1 MiB blocks and rewinds a
seekable upload; rows are never assembled as a whole-file dataframe.

## Preserved fields

Normalized facts preserve payer/member account, billing and usage windows,
service/product, line-item type, currency, unblended/blended cost, reservation
and Savings Plan identifiers/costs where present, discounts/credits/refunds/
taxes where present, and `raw_fields` plus source-row hash/evidence.

## State and idempotency

The PVT-003A `status` contract is used directly: `received`, `validating`,
`processing`, `quarantined` (awaiting account resolution), `reconciling`,
`completed`, and `failed` (partial/failure). A matching tenant+payer+file hash
replays a terminal import. A failed nonterminal import resumes using its same
import ID and deterministic part/fact IDs. Different hashes create a new import
and may reference `supersedes_import_id`; prior evidence is retained.

## Account safety and reconciliation

Active `cloud_account_mapping` records must exactly match the supplied
TenantContext. Unknown payer/member accounts produce tenant-owned quarantined
facts and an awaiting-resolution import; foreign mappings and mixed-payer CURs
fail closed. Reconciliation records source/normalized row counts, duplicate
counts, normalized total, currency, parser evidence, and reconciled or
quarantined status. No CUR-only utilization or rightsizing inference occurs.
