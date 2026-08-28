# PUE-ACT-002C - Universal Upload Admission and Structural Region Bootstrap

## Root cause

The Analyze Environment upload previously created a temporary prospect tenant
and then required legacy cost normalization to produce `ProspectAnalysis` before
any pilot scope could exist. A structurally valid enterprise workbook with no
legacy `cost`/`amount` alias therefore could not reach PUE Stage 1.

ACT-002C separates the paths after authorization and malware/container scan:

```text
authorized upload
  +-- legacy prospect normalization (unchanged authority)
  +-- upload-backed PUE admission (shadow, Stage 1/2 only)
```

Either path may fail without destroying the other. No legacy alias was added,
and no legacy `ProspectAnalysis` is manufactured.

## Upload-backed identity

`EvidencePilotAdmission` is derived from existing prospect consent context and
the physical evidence hash:

- `prospect_id`: temporary prospect tenant ID;
- `analysis_id`: fingerprint of prospect tenant ID, audit ID, and evidence hash;
- `organization_id` / `tenant_id`: absent for prospect-only evidence;
- `source_id`: opaque evidence-hash-derived ID;
- `file_id`: PUE-001 governed file ID;
- `evidence_fingerprint`: malware-scan SHA-256;
- `created_at` / `expires_at`: upload time and prospect retention expiry.

Filename and sheet names do not participate in semantic or provider identity.
An optional legacy analysis is only an external reference; it is not the PUE
identity source.

The local active-scope handoff explicitly identifies `UPLOAD_EVIDENCE` or
`PROSPECT_ANALYSIS`. Controls must match scope source, all four isolation fields,
and evidence fingerprint exactly.

## Structural region bootstrap

The bootstrap consumes the certified PUE-001 header candidate and observes
blank-separated row regions. The region containing the header becomes the
primary detail region. Where its leading identifier column is consistently
numeric, a later populated row that breaks that structural sequence is treated
as a footer boundary. Later blank-separated content remains a secondary summary
region.

For the inspected `CUR Jan 2026.xlsx` in `temp_uploads` this produces:

```text
Sheet                12345678
Header               row 5
Primary detail       rows 6-189 (184 records)
Footer               row 190 (excluded)
Secondary summary    rows 194-232 (separate)
```

The ten original headers, including `Price Per Service (USD)`, remain unchanged.
The pivot-like summary and Grand Total are never admitted as detail records or
used as governed aggregation authority.

## Stage behavior

Upload-backed Stage 1 displays original observed columns as **Observed - not yet
governed**. It does not turn structural headers into semantic truth. Stage 2
shows total cost as blocked because no governed monetary measure/currency mapping
authorizes aggregation. Neither the detailed values nor the workbook total are
rendered.

This admission also accepts non-monetary enterprise evidence such as Application,
Owner, Region, and Contract Renewal Date. Universal evidence admission has no
cost-column prerequisite.

## Authority and limitations

- Existing prospect normalization and its errors remain unchanged.
- PUE remains shadow/non-authoritative and capped at Stage 2.
- Header text containing `(USD)` is not converted into governed currency.
- No semantic mapping is auto-confirmed.
- No PUE numerical answer, FX conversion, recommendation, or Ask Nexora routing
  is introduced.
- Structural multi-region observation is sufficient for this pilot; full
  multi-table semantic fusion remains deferred.
- The workbook total near `861830.62008191` and earlier legacy `861828` history
  remain distinct and are not reconciled.
