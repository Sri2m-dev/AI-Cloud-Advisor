# P4.3.1 DEV Certification

Environment: `AI-Cloud-Advisor-Dev`
Project ref: `iafrrtmvvqmuksvprrsj`
Mutation policy: read-only certification; Production not accessed; CUR file #2 not
ingested.

## Account evidence

Account `727482365532` is unresolved and absent from the governed Cloud Account
Registry. The Financial Data Fabric account posture reports:

| Attribute | Value |
| --- | --- |
| Provider | AWS |
| Mapping status | unknown |
| CUR rows | 14,455 |
| Unblended spend | 37,143.2080151701 USD |
| Blended spend | 37,140.1799042241 USD |
| First usage | 2026-07-01 |
| Last usage | 2026-08-01 |
| Canonical ID | `cloud_account:e099f2ab-32d7-5f50-b03a-364c78d60098` |

No P4.2 classification result or evidence link exists for the account. Business unit,
owner, cost center, environment, application, and other unsubstantiated attributes
therefore remain `UNKNOWN`; no mapping metadata was invented. The canonical record
retains the AWS account identity, tenant-bound canonical identity, adapter lineage,
and provenance.

No deployed legacy canonical source-map record was available, so no relationship was
asserted. Relationship state remains empty/unknown rather than inferred.

## Financial invariants

The bounded DEV import history reports one import, 786,745 CUR facts, total cloud
spend of 127,678.2170275708 USD, and reconciliation variance of exactly 0 USD. This
certification performed no mutation, so before and after values are identical.

## Migration status

`supabase migration list --linked` confirms local and DEV histories are aligned through
`202608090007`. P4.3.1 adds no database migration.

## Operational note

The broad billing-classification-evidence RPC exceeded its statement timeout during
read-only inspection. Direct classification-result and evidence-link checks completed
and returned no evidence for the selected account. The registry degrades to documented
`UNKNOWN` state rather than fabricating a classification.

## Performance envelope

A deterministic local 500-entity benchmark measured canonical detail lookup at
0.087 ms, registry search at 41.764 ms, and composed detail/relationship retrieval at
0.496 ms. These results are within the P4.3.1 limits of 250 ms, 1 s, and 2 s.

## Population remediation

Browser investigation on 2026-08-11 confirmed that an unconfigured development
runtime correctly selected the SQLite fallback, whose governed local domain tables
contained zero rows. The empty page was not caused by tenant filtering and no local
row was synthesized to conceal the missing source data.

With the valid `AI-Cloud-Advisor-Dev` Supabase runtime selected, the same tenant-scoped
composition projects 67 discovered cloud accounts from
`tenant_cloud_account_posture`. Account `727482365532` is present as
`cloud_account:e099f2ab-32d7-5f50-b03a-364c78d60098`; the populated page renders all
67 records without a traceback. The UI now identifies the selected repository mode.

Populated execution also revealed a Versions-tab serialization defect: Python's
generic dataclass conversion attempted to deep-copy immutable mapping proxies. The
page now serializes dataclass fields, enums, mappings, and collections recursively,
preserving immutable version evidence without copying or mutating source records.
