# NXR-DASH-RC-01 approval register

Status: **STAGING BLOCKED**. Production **NO-GO**. Azure Start Discovery **BLOCKED**.
No organizational approval evidence was found in the reviewed NXR-DASH-08/09/10 sources.
Every decision below remains **PENDING**; implementation and synthetic test results are not approval.
Accountable owners are roles; no named approver or signature is invented.

| Decision | Exact implementation dependency | Secure recommended option | Accountable owner | Evidence / minimum approval action |
|---|---|---|---|---|
| D1 trusted grant issuer | SQL `require_approved_authority`/`authorize`; backend `tenant_verifier` and `existing_read_grant_lookup` | Separate trusted JWT/session verifier and request-bound capabilities; current `users.auth_user_id` membership, never email or service-role bypass | Security + identity owner | PENDING; no approval. Sign issuer identity, verification/revocation contract and capability binding; name approved implementation and provisioning procedure. |
| D2 independent retained-source attester | `source_attestation`; `certify`; independent reconciliation observations before publication | Separate attester/reconciler authorities observing immutable retained bytes; no copy from normalized totals | Data evidence + security owner | PENDING; no approval. Sign attester identity, storage/version/hash convention (including gzip), parser/precision and reconciler authority; provide independently verifiable fixtures. |
| D3 backend read privilege | Private-table access and versioned read RPC; backend read client/transport | Dedicated least-privilege reader, explicit scoped capability check, no privileged caller ownership or RLS bypass authorization | Database + security owner | PENDING; no approval. Sign role/privilege matrix and approved authority-hook replacement, confirm server support and test plan. Do not merely remove denial or grant service_role. |
| D4 backend refresh/publish privilege | Versioned refresh RPC and ledger/membership/pointer writes | Separate publisher unable to mint grants or attestations; no publish operation on page render | Database + security owner | PENDING; no approval. Sign publisher permissions, wrapper ownership and deployment procedure; authorize only a separately reviewed implementation. |
| D5 writer coordination | `scope_lock`, canonical mutation triggers, serializable refresh, expected-generation checks and deferred guards | Every relevant writer participates in same scoped mutation protocol; validate deadlock/retry and absent-pointer cases | Ingestion + database owner | PENDING; no approval. Approve all-writer inventory, lock encoding/protocol, digest representation and target-server race/rollback acceptance. |
| D6 generation-pinned dashboard reader | `AwsFinancialReadBackend`, `AwsFinancialReadSelection`, `aws_financial_dashboard_status`, active command panel | Server-owned coverage/query and existing read-grant lookup; new captured canonical envelope each render; preserve P1 | Dashboard + contract owner | PENDING; no approval. Review RC code/tests and sign exact backend bootstrap bindings, allowed dataset/query coverage and page acceptance evidence. |
| D7 session/transaction policy | `require_approved_authority`, verifier session freshness, read transport isolation and retry policy | Authoritative real UUID/session revocation checks; repeatable-read read-only reads; serializable publish with bounded retry | Identity + database owner | PENDING; no approval. Sign session freshness/revocation, role-to-permission policy, renewed capability rules and actual hosted transport/isolation integration. |
| D8 source/evidence retention | Retained references, immutable ledgers and authority history, RESTRICT FKs, audit sink/cleanup and response bounds | Retain all active/referenced evidence, restricted lifecycle, independent post-rollback failure audit | Data governance + security owner | PENDING; no approval. Sign retention duration/storage/version guarantees, audit access, response limits, deletion and rollback procedures. |

Approval evidence must identify decision ID, named accountable approver, scope/environment,
chosen option, reviewed artifact hashes/version, date, conditions and durable evidence reference.
Record approvals through the organization's review process; this register does not grant privileges.
Any rejection must specify the concrete changed boundary. Any unresolved row blocks staging activation.

## RC implementation closure

The active route now calls the panel's backend-owned read composition. Server bootstrap can
supply only an explicit typed backend containing a current tenant verifier, canonical coverage
reader, read client and lookup of existing read capabilities. No page/session setting populates
it. No backend is installed by this task. The SQL default-deny hook and runtime revokes remain.
Each render verifies subject before coverage or RPC, binds scope/actor, permits only read RPC,
and builds a fresh adapter; it never calls ingestion/refresh or invents receipt/snapshot/source.
Ready evidence displays source, currency/period, total, coverage and persisted timestamp.
Missing authority/data, stale evidence or foreign selection displays NOT_READY/UNKNOWN.

Local release code is prepared for reviewed backend dependency installation; hosted composition
and real identity/capability availability are **not activated or validated**. D6 remains pending.
Existing P1 and other dashboard metrics are unchanged; the AWS panel has no legacy/demo fallback.

## Preservation and local checks

Branch `program/nexora-production-activation`; HEAD `3b4a1100d86ef05dd915cf1734a2c4fa6581c299`;
recorded upstream 12 ahead / 0 behind, without fetch. Initial 2108 Git-listed files aggregate
SHA-256 `93ba4e0a1bfe0dd42c7987efd737993a767662d3f94e28d52459ac777f62355e`
(sorted path/raw-byte SHA-256 map, sorted compact JSON UTF-8, then SHA-256).
Only the four allowed composition files and focused new tests are changed, plus these two RC docs.
SQL contracts, migrations, auth, CUR engine, repository, prior reports and manifest are preserved.
Manifest remains BLOCKED, executable=false, postgres_replay=NOT_EXECUTED.

Focused offline execution covers active-route function wiring, complete synthetic wire evidence,
identity/tenant rejection, stale/source/snapshot failures, missing read grant, page read-only
allowlist and matching versioned SQL/transport parameter names. These are not hosted Auth/RLS
or new PostgreSQL execution results. No local database was needed for these composition edits;
the prior 13 PostgreSQL results remain historical evidence. Final counts are in the staging runbook.
