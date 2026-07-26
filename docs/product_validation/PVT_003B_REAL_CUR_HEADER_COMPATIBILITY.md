# PVT-003B Real CUR Header Compatibility

Status: header remediation certified locally; exact-head hosted CI pending.
No real CUR data was written to DEV.

## Canonicalization

`aws-cur-v1` has one explicit, fail-closed alias table. Slash-form AWS CUR
headers and the observed underscore-normalized headers resolve once to 28
internal semantic names before validation. Downstream processing uses those
names only. Duplicate source aliases for one semantic field are rejected as
ambiguous. UTF-8 BOM is removed by `utf-8-sig` for both CSV and CSV.GZ.

The actual 131-column structure is represented by the header-only fixture
`tests/cur_ingestion/fixtures/aws_cur_normalized_131_headers.csv`. It contains
no customer rows, account IDs, resource IDs, costs, or tags.

## Actual header classification

All 11 required profile semantics are **ALIASED**:

- payer and usage accounts;
- billing-period and usage start/end;
- service and product code;
- line-item type;
- unblended cost and currency.

Fourteen optional normalized semantics are also **ALIASED**:

- region, availability zone, resource ID, usage type, operation, usage amount,
  and pricing unit;
- blended cost and total discount;
- Reservation ARN/effective cost;
- Savings Plan ARN/effective cost;
- resource tags.

Three supported optional semantics are **ABSENT** as dedicated columns:
credit amount, refund amount, and tax amount. Credit/refund/tax meaning is not
fabricated; corresponding line-item types remain preserved.

The other 106 columns are **PRESERVED_RAW / UNSUPPORTED_OPTIONAL**. Each remains
in `raw_fields` and participates in deterministic source-row identity, but is
not promoted to a first-class financial column. They include billing metadata,
capacity-reservation details, net rates/costs, pricing terms, expanded product
attributes, detailed Reservation/Savings Plan commitments, split-line-item
fields, cost-category data, and additional tag payloads.

## Read-only real-file evidence

Both files are comma-delimited UTF-8 BOM gzip exports with the same 131-column
header and July 2026 billing scope (`2026-07-01T00:00:00.000Z` through the
exclusive end `2026-08-01T00:00:00.000Z`). Each has one payer, 67 member
accounts, and USD currency.

| Evidence | File 00001 | File 00002 |
|---|---:|---:|
| Bytes | 147,995,148 | 148,026,501 |
| Rows | 786,745 | 786,746 |
| SHA-256 | `709f678abc1975aedb4643ec896bd564bcbb51c34822db6c4172bf037776a319` | `7761d12df7de9da45202dcdc093126960c1d897e2b0874195e9aa43fa80958f8` |
| Services | 66 | 65 |
| Product codes | 67 | 68 |
| Resource-ID rows | 636,111 | 635,483 |
| Savings Plan ARN rows | 11,997 | 11,903 |
| Tax line items | 773 | 723 |
| Total unblended cost (profile only) | 127,678.21702757080 | 146,318.50778495500 |

Line-item types are Usage, Tax, BundledDiscount, SavingsPlanCoveredUsage,
SavingsPlanNegation, and SavingsPlanRecurringFee. Neither file has Credit or
Refund line-item types. Reservation ARN is empty; Reservation effective-cost
and Savings Plan fields are present. Resource tag payload columns are present.

The files are **materially different same-period exports**, not byte or row
duplicates and not sequential CUR parts. Headers match, but zero rows match at
the same position, the financial totals differ, and service/product/line-type
distributions differ. This evidence cannot safely designate either file as the
authoritative corrected version; Owner selection remains required before any
real-CUR DEV ingestion.
