# Nexora Prospect Data Intake

## Purpose

Prospect Data Intake creates a temporary, isolated analysis from prospect-provided cost
evidence. It does not write to demo datasets or customer production tenants. Every screen and
export is classified as **Prospect Demonstration · Temporary Analysis · Not Certified Production
Data**.

## Authorized operators

Only the canonical `sales_engineer` and `finance` roles may create or process a prospect tenant.
Executives can receive a watermarked output but cannot upload, alter, or delete source evidence.

## Supported v2.0 inputs

1. AWS billing/CUR-derived CSV
2. Azure cost export
3. GCP billing export
4. SaaS/license CSV or Excel
5. Generic technology-cost Excel/CSV
6. Manual invoice/bill spreadsheet

Only `.csv` and `.xlsx` files are accepted. Files are limited to 25 MB and 500,000 rows.
Executable content, macro/embedded binary spreadsheet content, malformed XLSX containers,
oversized expanded workbooks, and known test malware signatures are rejected before parsing.

## Encryption and secret management

Set `NEXORA_PROSPECT_DATA_KEY` to a Fernet key held by the deployment secret manager. Generate a
key with `services.prospect_data_intake_service.generate_encryption_key()`. Production fails closed
when the key is absent or invalid. Local development creates `.streamlit/prospect-data.key`, which
is excluded from Git.

Each prospect tenant receives a unique data-encryption key wrapped by the deployment master key.
Uploaded sources, normalized canonical rows, analyses, and audit events are encrypted at rest.
Source filenames and row content are not written to application logs or audit details.

## Truthfulness and value maturity

Attribution not supported by supplied evidence remains `UNKNOWN`. Opportunities progress through:

- Identified
- Evidence Qualified
- Recommended
- Approved
- Realized

An amount is not promoted beyond Evidence Qualified by intake. Recommendation, approval, and
realization require the existing governed services and accountable human authority.

## Retention and purge

The default retention period is 30 days and may be configured from 1–90 days by an administrator.
Schedule the following command at least daily:

```powershell
.\.venv\Scripts\python.exe scripts\purge_expired_prospect_data.py
```

Purge cryptographically erases the tenant key and removes the complete encrypted tenant directory,
including source evidence, normalized data,
analysis, reports, conversation context, caches, and temporary exports if present. A minimal
non-sensitive tombstone retains only Tenant ID, Audit ID, event type, and purge timestamp.

## Data-use restriction

Prospect evidence is not copied into persistent demo fixtures, model-training datasets, shared
analytics stores, or other tenants. AI answers on the intake page are deterministic summaries of
the current tenant analysis; no uploaded content is sent for training or cross-customer reuse.
