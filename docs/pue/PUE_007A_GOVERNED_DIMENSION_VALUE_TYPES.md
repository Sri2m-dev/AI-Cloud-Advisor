# PUE-007A — Governed Dimension Value Types

## Purpose and boundary

PUE-007A closes the filter-compatibility gap before natural-language intent
interpretation. A governed dimension now explicitly states its certified
normalized representation, whether it is filterable, and the bounded operators
permitted for that representation.

This amendment validates already-structured filters. It does not interpret
language, coerce values, discover semantics, add query capabilities, scan rows
during planning, execute queries, resolve entities, change UI pages, or persist
production data.

## Certified value-type model

PUE-005 derives one `DimensionValueType` from valid PUE-004 normalized records:

- `STRING`
- `INTEGER`
- `DECIMAL`
- `BOOLEAN`
- `DATE`
- `DATETIME`

PUE-004's `CURRENCY_CODE` representation is governed as `STRING`; its uppercase
ISO normalization remains an upstream responsibility. Unknown, absent, or mixed
normalized types do not produce an arbitrary winner. The dimension becomes
`BLOCKED`, non-filterable, and carries
`DIMENSION_VALUE_TYPE_CONFLICT`.

## Operator compatibility

The initial versioned matrix is intentionally narrow:

| Value type | Allowed operators |
|---|---|
| `STRING` | `EQUALS`, `NOT_EQUALS`, `IN` |
| `INTEGER` | `EQUALS`, `NOT_EQUALS`, `IN` |
| `DECIMAL` | `EQUALS`, `NOT_EQUALS`, `IN` |
| `BOOLEAN` | `EQUALS` |
| `DATE` | `EQUALS`, `DATE_FROM`, `DATE_TO` |
| `DATETIME` | `EQUALS`, `DATE_FROM`, `DATE_TO` |

The policy does not add greater-than, less-than, between, fuzzy matching, or
other mathematically possible operations.

## Exact structured-value validation

PUE-007 validates filter values against the selected governed dimension:

- `STRING` requires a Python string.
- `INTEGER` requires an integer and does not accept Boolean values.
- `DECIMAL` requires `Decimal`.
- `BOOLEAN` requires `True` or `False`.
- `DATE` requires a date that is not a datetime.
- `DATETIME` requires a datetime.
- `IN` requires a non-empty tuple whose every member matches the certified type.

There is no coercion. Strings such as `"123"`, `"true"`, and `"2026-01-01"`
are not converted by planning. Normalization belongs upstream in PUE-004.

String matching remains literal. The amendment does not infer that `EC2` is an
AWS service, expand aliases, change case, or resolve entity identity.

## Versioning and stale authority

The dimension value/operator policy has an explicit version. Certified type,
operator set, filterability, and policy version participate in the dimension
fingerprint. Dimension identity flows into assessment, alignment, execution
authorization, and analytical plan identity through the existing certified
chain.

A type conflict, type change, or operator-policy version change therefore
creates a new current assessment. Prior execution authorizations fail current
authorization checks, and intents tied to the previous assessment plan as
`STALE`.

## PUE-008 readiness

PUE-008 may eventually translate natural language into a structured intent, but
it must emit already-normalized typed filter values. PUE-007A only answers
whether that structured value and operator are compatible with the governed
dimension. It provides no natural-language or execution authority itself.
