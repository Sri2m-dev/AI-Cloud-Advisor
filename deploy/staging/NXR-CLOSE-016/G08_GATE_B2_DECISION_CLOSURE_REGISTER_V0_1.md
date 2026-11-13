# NEXORA CLOSE-016 — G08 Gate B2 Decision Closure Register v0.1

Prepared: 27 October 2026, Asia/Calcutta. DOCUMENTATION ONLY; not executable implementation authority.

**PO POLICY DIRECTIONS APPROVED. GATE A TECHNICAL CLOSURE PENDING. GATE B2 EXECUTABLE IMPLEMENTATION ON HOLD. STAGING EXECUTION NO-GO. PRODUCTION NO-GO.**

## 1. Authority, sources and decision boundaries

This single new register is authorized by the user's supplied instructions and follow-up. Product Owner policy approval is recorded as reported by the user. No personal name, signature, approval date/time, independent review or technical acceptance is invented. The preparation date above is not an approval date. This register does not modify original approval sheets, source specifications or certified artifacts.

All four source SHA-256 values matched before writing, including a recheck after the interrupted preparation turn:

| Read-only source | Verified SHA-256 | Relevant evidence |
|---|---|---|
| [Gate A design v0.1](G08_GATE_A_DESIGN_V0_1.md) | a092fa13c30721e5857b15ca1d266671394463cbe96ec7175c65f1ee8d149cf8 | 62–203 contracts; 245–283 review/gates |
| [Contract resolution v0.2](G08_GATE_A_CONTRACT_RESOLUTION_V0_2.md) | 5678647989ad9659311700d55f2b28e50fdc2fc0d420f1d080a45ea0dbc554cf | 14–242 contract directions; 244–292 provisional inventory |
| [Technical annex v0.1](G08_GATE_A_TECHNICAL_ANNEX_V0_1.md) | 98b9feaac3d0abab86d7c58c98b2336436c7a642f13cb27ee3ed3a23b72f47da | 38–353 proposed administration; 355–478 retention; 480–545 vectors; 547–650 consumers/dependencies |
| [B1 implementation readiness v0.1](G08_GATE_B1_IMPLEMENTATION_READINESS_V0_1.md) | feae2daf70da4e1452ab9cb1ae634a6e3a372040e05d65d53ec830aaf9022d73 | 30–108 open contracts; 110–214 inventory/acceptance; 216–254 B2 criteria/stops |

ESTABLISHED = source/document evidence, not deployed behavior. PO APPROVED = reported policy direction only. PROPOSED = recommended engineering resolution. OPEN = actual implementation-determining decision/evidence absent. CLOSED—PO PRINCIPLE does not mean CLOSED—TECHNICAL CONTRACT. No technical disposition is preselected.

### PO-approved directions and principles

| ID | Reported PO decision | Boundary still requiring technical acceptance |
|---|---|---|
| P01 | R01–R09 recommended directions approved, subject to exact technical contracts | Approved direction does not freeze raw fields, guards, administration, retention or file scope |
| P02 | Archival fails closed unless authorization is valid and unrevoked, no active legal hold remains and applicable retention period is satisfied | Actual durations, authoritative hold evidence, predicate and transaction design OPEN |
| P03 | Hold-clearance actor differs from archival-authorization actor, compared using Auth UID | Must define exact relied-upon clearance event set and enforce each comparison; no UUID supplied by caller is authoritative |
| P04 | Immutable evidence of actor, scope, reason, policy version, supporting evidence and event references | Required columns, constraints, access/retention and version reconstruction need accepted design |
| P05 | Authorization, retention eligibility and holds are revalidated inside protected transactions | Exact lock/time/isolation/authority checks OPEN |
| P06 | Missing, expired, revoked or unverifiable authorization, unresolved external holds or uncertain eligibility denies archive | No external hold availability/freshness guarantee is invented |
| P07 | Archive does not implicitly delete identity bindings, audit history or evidence; deletion needs separately approved process | Retention/deletion obligations and any future purge procedure remain OPEN |

P01–P07 are CLOSED—PO PRINCIPLE as reported in the current instructions/conversation. P03–P07 are the five additional retention directions reported by the user. Their technical realization is OPEN; the register does not claim earlier source documents already contain these approvals. Pairwise routine stewardship SoD and RESTRICT/deny-first directions remain approved directions, not independent Database/Retention acceptance.

### Additional PO policy dispositions — approved 28 October 2026

Source: the user's explicit PO decision-recording instruction reports approval on 28 October 2026. These are PO policy directions, not independent technical acceptance. No reviewer identity, signature or precise approval time is supplied or inferred.

| Decision ID | PO disposition | Approved policy direction |
|---|---|---|
| DD-01 | APPROVED | Owner-controlled root bootstrap with independent approval and immutable evidence. |
| DD-02 | APPROVED | Verified root succession, fail-closed root loss and controlled recovery. |
| DD-03 | APPROVED | Distinct natural persons for sensitive bootstrap/recovery approvals, plus applicable Auth UID checks. |
| DD-05 | APPROVED | Prefer bounded function ownership; broader privileged ownership requires separate acceptance. |
| DD-09 | APPROVED | Scoped SERVICE-01 replacement for authenticated human RPCs. |

#### PO-D10 — APPROVED — PRODUCT OWNER POLICY ONLY

Source: the user's explicit PO-D10 decision-recording instruction. This entry does not infer an approval date from the preceding 28 October 2026 dispositions.

Policy: Routine global identity-administrator grant, revise and revoke operations require independent approval before execution.

The requester and approver must be distinct natural persons, with applicable Auth UID separation checks.

This requirement supplements the previously approved owner-controlled bootstrap, succession and recovery policies. It does not weaken existing safeguards.

The approval does not establish or accept:

- The exact approval workflow or approval matrix.
- Approval evidence schema, storage or validation.
- Executor permissions or independence requirements beyond the approved requester/approver separation.
- Function signatures, role privileges or database ownership.
- Transaction, locking, replay or failure-handling algorithms.
- Any implementation or release authorization.

Identity/Security, Database and Application engineering must resolve and independently review the implementation-determining contracts.

#### PO-D11 — D02/D03 Proposed Design Direction Approval — APPROVED — PRODUCT OWNER POLICY ONLY

Authority: Product Owner — explicit approval in the current conversation. Recorded: 30 October 2026, Asia/Calcutta. This is the recording date, not an inferred independent review date or signature.

Approved source documents (exact versions and SHA-256 values verified before recording):

| Approved architectural-direction source | SHA-256 |
|---|---|
| [G08_D02_D03_IMPLEMENTATION_CONTRACT_CANDIDATE_V0_1.md — D02/D03 Implementation Contract Candidate v0.1](G08_D02_D03_IMPLEMENTATION_CONTRACT_CANDIDATE_V0_1.md) | 438a31d4d689e5ea1c41b2d61365d25eb7796e8245cd3139150b19a2b3a6520c |
| [G08_D02_D03_DATABASE_RESOLUTION_ADDENDUM_V0_1.md — D02/D03 Database Resolution Addendum v0.1](G08_D02_D03_DATABASE_RESOLUTION_ADDENDUM_V0_1.md) | 51327f26eefc7c20d952ddeeb233ae252bacea68a88d94c5a1ef35d56c112300 |

Product Owner decision: The Product Owner approves the proposed architectural direction below and authorizes progression into independent technical review:

1. D02 identity-administrator lifecycle and immutable history.
2. D03 bounded function ownership and least-privilege enforcement.
3. DBR-01 deferred composite foreign keys and transaction-end consistency checking.
4. DBR-02 separate owner-operation authorization and immutable receipt records.
5. PO-D10 independent approval requirements remain mandatory.
6. Existing DD-01/DD-02/DD-03/DD-05/DD-09 policy decisions remain preserved.

This approval does NOT:

- Establish missing implementation-determining definitions.
- Constitute independent Database, Identity/Security or Application technical acceptance.
- Qualify target Supabase/PostgreSQL behavior.
- Authorize SQL execution, implementation, migrations or deployments.
- Close D02/D03 or any other D01–D12 item.
- Change Gate A, Gate B2, Staging or Production status.

Outstanding OPEN—DESIGN conditions remain explicit: complete physical fields/keys/FKs and mode-specific history/receipt consistency; circular-reference and transaction-end checker implementation covering the complete affected administrator history, including unexpected extra/missing versions, events, receipts and approval links, without checker privileges/RLS concealing inconsistency; truthful owner-mode operator attribution and owner receipt/authorization interfaces; approval authority, natural-person verification, requester/approver/executor/validator matrix and evidence authenticity; validity/succession/recovery and incident ownership; complete bounded owner/grant/RLS/helper/overload definitions; writer and indirect root-invalidation coverage; locking throughput and transaction semantics; canonicalization vectors, replay/read rights, membership evidence, consumer dispositions and D01/D04–D12 dependencies. Approval of direction does not select unresolved alternatives or supply organizational/operational facts.

Outstanding OPEN—QUALIFICATION conditions remain explicit: target managed-role and ownership-transfer feasibility; effective privileges/defaults/inheritance/role-switch paths; RLS and SECURITY DEFINER/trigger execution context; deferred FK/checker firing, visibility, rollback and concurrency; advisory-lock/snapshot behavior; operator authentication/session binding; API/helper exposure; qualified SHA/canonicalizer interoperability and effective-denial behavior. No target capability or test result is inferred.

Independent technical acceptance remains PENDING:

| Reviewer function | Required independent scope | Required disposition |
|---|---|---|
| Database Engineering | Physical references and deferred constraints; complete-history transaction-end checker; bounded privileges/RLS; locks, atomicity, intermediate states and target qualification conditions | ACCEPT / REJECT / CONDITIONALLY ACCEPT — PENDING |
| Identity/Security | PO-D10 enforcement; approval authenticity and natural-person separation; owner authorization/operator authentication; root recovery, escalation and bypass boundaries | ACCEPT / REJECT / CONDITIONALLY ACCEPT — PENDING |
| Application Engineering | RPC/wire/canonicalization contracts; immutable human/owner receipts; replay/unknown-commit outcomes; session-local clients and application consumer dependencies | ACCEPT / REJECT / CONDITIONALLY ACCEPT — PENDING |

Each actual clause disposition must record reviewer identity/function, review date/timezone, exact document/version/hash, evidence examined, technical rationale, outstanding conditions and accountable owners. No reviewer identity, evidence, signature or acceptance result is populated here. Conditional acceptance must identify precise accepted/blocked scope and cannot release implementation with an unresolved implementation-determining condition. Independent Certification review of provenance, verification/evidence scope and final frozen inventory remains required under D12; PO approval does not replace that function.

D01–D12 remain OPEN. Gate A PENDING. Gate B2 ON HOLD. Staging NO-GO. Production NO-GO. Technical acceptance is PENDING; separate implementation/release authorization remains absent.

DD-04, DD-06, DD-07, DD-08 and DD-10 remain recommendations, not approved technical decisions. No broader privileged-owner exception is approved. The exact SERVICE-01 replacement scope, interfaces, privileges and acceptance criteria remain unresolved.

D02 and D03 remain OPEN; all D01–D12 blocker groups remain OPEN. These dispositions do not satisfy pending technical-review requirements, freeze implementation scope or authorize executable work. Gate A remains PENDING; Gate B2 implementation remains ON HOLD; Staging and Production remain NO-GO.

No independent technical acceptance is inferred for exact retention periods, legal-hold source, verification/enforcement of the approved natural-person policy, owner privileges, administrator version storage, provisioning treatment, successor scope or hosting. Existing G08/G09/checkpoint records remain unchanged and require actual reconciliation through separately authorized recording.

## 2. Exact retention contract under review

ESTABLISHED: v0.2:125–154,205–242 and annex:370–478 propose lifecycle/hold/authorization structures; their SQL is illustrative and unexecuted. Existing S024 admits superseded→archived using a generic transition permission, not the proposed retention controls. Source reference: deploy/staging/NXR-CLOSE-014/sql/024_0020_create_stewardship_rpcs.sql:55–62. No hosted retention policy or external hold system was inspected.

### State and event transitions

| Entity | Proposed transition | Authority and evidence required | Status |
|---|---|---|---|
| Hold | absent→OPEN | Current scoped retention administrator, DB-derived actor, exact review/domain/scope, policy version, reason and external/supporting evidence reference; immutable open event | Engineering detail OPEN; fail-closed principle approved |
| Hold | OPEN→CLEARED | Explicit clearance of exact open_event_id/hold_id; current authorized clearer; immutable clearance evidence; original open event retained | Clearance authority/evidence OPEN; no implicit timeout clearance |
| Hold | CLEARED→new OPEN | New hold_id/open event; never overwrite a cleared hold or delete its history | Proposed; review required |
| Archive authorization | absent→ISSUED | Current scoped issuer, exact review and supersession event, accepted policy version, retention eligibility evidence, clearance references, not_before/expires_at and immutable issuance | Issuance contract OPEN |
| Archive authorization | ISSUED→REVOKED | Accepted revoker authority, reason, immutable revoke event referencing issuance; no in-place history edit | Revoker policy OPEN |
| Archive authorization | ISSUED→not currently valid | Decision time outside [not_before,expires_at), invalid issuer/parent, policy/hold uncertainty or unverifiable evidence; no archive | Denial principle approved; exact historical authority semantics OPEN |
| Review | superseded→archived | Valid lifecycle actor AND valid retention authorization AND confirmed eligible period AND no active/unresolved hold AND protected transactional recheck | PO policy approved; engineering acceptance OPEN |
| Review | archived→other state | Forbidden under proposed lifecycle; no reopening power | Direction retained; technical guard OPEN |
| Identity/audit/evidence | archive→deletion | No implicit transition; separately approved deletion process required | PO principle approved; deletion design not authorized |

Proposed archive decision input is the strict v2 mutation with retention_authorization_id, review_id, scope, expected revision, rationale and one evidence_references source; actor derives from auth.uid(). Authorization must bind the same review/domain/org/tenant and exact supersession event, not merely a matching tenant. Policy version must refer to an accepted immutable policy definition; a caller string naming an unknown version is not eligibility evidence.

### Transactional archival predicate — PROPOSED, NOT IMPLEMENTED

1. Authenticate current user; validate strict request/digest; acquire accepted current profile/authority/organization locks in the agreed order. Verify active membership and applicable lifecycle/domain authority.
2. Lock the affected review and the same hold/authorization serialization boundary used by issuance, clearance, opening and revocation. Refresh state/revision and use one defined decision time AFTER waits. Exact database isolation and row/advisory locking protocol remain D02/D03/D06 decisions.
3. Resolve exact immutable issuance, current revocation state, policy definition, issuer/version/parent lineage and required retention-start evidence. Verify scope/review/supersession reference, validity interval, evidence integrity/freshness and no active holds. Unknown or unavailable external-hold state is denial, not an empty hold list.
4. Resolve every clearance event relied upon by this authorization. Compare each clearance actor's stored DB-derived Auth UID with the issuance actor's Auth UID; any equality denies. A reviewer must define the exact clearance set/window and evidence references. No observed holds may make this comparison vacuous, but never proves unknown external holds absent.
5. Revalidate authorization, period and holds under those locks immediately before new mutation. Check expected revision for a new operation, then update once and append exactly one scoped immutable review event/receipt with policy, actor, issuance and clearance references. A concurrent hold/revoke serialized first denies; one serialized after an already committed archive does not rewrite past events.
6. Replay never creates a new archive. Use original immutable edge/receipt plus accepted current-authority policy. Revoked or uncertain authority must not return success via an unreviewed replay bypass. Historical receipt read rights are separately governed by R09.

No accepted durations or retention-start date are available. OPEN alternatives for the period clock include supersession time, source-record age or another Data/Retention-defined event; recommendation is an explicitly versioned review-specific policy with an immutable start event. No duration is supplied by Codex. Exact inclusive/exclusive boundary, policy replacement, legal exceptions and historical authorization expiry effects must be decided rather than inferred from examples.

External legal holds: OPEN choices are an authoritative synchronized register with accepted freshness/completeness evidence or a formally approved manual evidence/attestation workflow. Recommend a defined authoritative source and fail closed when fresh completeness cannot be established. Neither this register nor the local proposed hold table guarantees all external holds are known. Clearance evidence standards, signer authority, acceptable evidence retention and hold reinstatement remain Data/Retention+Identity/Security decisions.

## 3. Security invariants and technical-review status

| Invariant | Proposed enforceable contract | Technical review still required |
|---|---|---|
| Deny by default | Exact authenticated RPC EXECUTE/USAGE; no ordinary direct profile/authority/history INSERT/UPDATE/DELETE; private helper revokes; effective inherited/default/column grants inventoried | Database + Security, D03 |
| DB-derived actor | auth.uid() + current UID-bound active profile/org + active scoped authority; no request actor/role as evidence | Database + Identity, D03/D09 |
| Auth UID SoD | Routine approver!=submitter, promoter!=approver; clearance actor!=issuance actor for all relied-upon clearance events; immutable actor provenance | Domain + Identity + Retention, D04/D06 |
| Immutable history | Version/event/receipt/hold records append-only; scoped references and actor/policy/digest/reason snapshots; no fabricated legacy cycles | Database + Retention, D04/D07/D08 |
| Cross-scope isolation | Canonical org=tenant; review/domain/subject/parent references match; scoped composite FKs or accepted guarded checks | Database + Security, D02/D04 |
| Last-root safeguards | Concurrent last-root revocation denied; expiry/root loss requires accepted owner recovery; no automatic renewal | Database + Identity, D02 |
| No trusted caller GUC | No caller-set custom session flag, JSON claim or generic patch grants protected-write authority | Database + Security, D02/D03 |
| No service-role fallback | Human mutations use isolated user client; shared anonymous/service client cannot impersonate context actor | Application + Identity, D03 |
| Transaction-safe rechecks | Same lock protocol for admin, membership, parent/hold/revoke and business mutations; current validity read after locking | Database + Security + Retention, D02/D04/D06 |
| Unknown commit | Stop and retain uncertainty; reconcile using separately approved read/receipt rights; never generate a fresh key or compensate blindly | Application + Database, D08/D10/D12 |
| Deprovision deny-first | DB inactive/revoked lineage committed before separately authorized Auth disable/revoke; Auth failure cannot reactivate membership | Identity + Application + Database, D09 |
| Administrative limits | Owner/BYPASSRLS compromise is outside ordinary tenant-caller guarantee; RLS is not proof against the owner | Database + Security, D03 |

These invariants are design obligations, not tested outcomes or deployed facts. Current G08 decision sheet:114–136 accepts conditional CASCADE and server-only access; current G09_TECHNICAL_REVIEW.md:7–31 proposes service-role SELECT. Their replacement/reconciliation is not accomplished by changing terminology in this new register.

## 4. Contract resolution matrix — R08 assessed last

Every technical disposition below is UNSELECTED: ACCEPT / REJECT / CONDITIONALLY ACCEPT. All rows retain **PO DIRECTION APPROVED / TECHNICAL CONTRACT OPEN**. Independent reviewer identity/function/date/evidence are not supplied by the reported PO approval.

| ID / approved direction | Exact outstanding decision / proposed default | Accountable reviewer / required evidence | Impacted implementation / blocker IDs |
|---|---|---|---|
| R01 bounded roles, item wins, approval guard consistency | Complete field types/null/default/limits, account/status/expected-state normalization and exact raw alias behavior. Default v0.2 bounded table and item-overrides-shared in preview/commit/direct RPC | Application + Database + Identity; exact raw-role/field truth tables and invalid/override examples. Sources v0.2:14–44; B1:30–50; services/cloud_account_registry_service.py:19–50,205–289 | S011/S013/S020, registry service/repository/composition, raw role handling; D01 |
| R02 authenticated-user stewardship | Exact owner/overload/ACL/RLS/helper/schema/API model and SERVICE-01 disposition. Default user RPC-only wrapper, SQL-side validation, no shared fallback | Database + Identity/Security + App; privilege/signature matrix, current membership/session assurance and actual disposition. Sources v0.2:46–68; annex:305–322; G08 sheet:126–136 | S024, A020A/A023A helpers/grants, user_client module; D03/D09 |
| R03 separate identity root, scoped authority, immutable versions | Root lifecycle, bootstrap/succession/loss/last-root guards; trusted-write/lock semantics; exact object placement/admin requests. Default controlled owner functions + independent bootstrap evidence, never role/email seed | Database + Identity + App + Domain; admin trust/state/guard algorithms and artifact/object map. Sources annex:38–353,355–368; B1:52–81 | S020/A020A/A023A, identity administration and bootstrap/orchestration scope; D02/D07/D08/D12 |
| R04 pairwise routine Auth UUID SoD | Current-vs-historical expiry/material change, assignment replacement, held status and natural-person limits. Default no approval resurrection, one cycle/no reopening, pairwise rule unchanged | Domain + Identity + Database; event/version/parent linkage and expiry/held examples. Sources v0.2:109–123; annex:472–478; S024:55–62 | Authority/version/cycle/audit and S024/read logic; D04 |
| R05 proposed lifecycle/P inheritance and fail-closed archive | Exact replacement same-subject scope/state/lock rules; policy/period/hold/authorization predicate. Default state-only canonical, no hidden entity mutation or deletion | Domain + Retention + Database + Identity; complete edge matrix and replacement/archival examples. Sources v0.2:125–154; annex:370–478; WP-005:184–225 | S024 and A023A retention/holds/authority; D04/D05/D06 |
| R06 strict v2/full DB-bound fingerprints | Business/admin field completeness, Unicode/numeric/size/direct JSONB limits, qualified SHA dependency, receipt retention and legacy compatibility. Default single evidence source and DB recomputation; no lexical guarantees JSONB cannot supply | Database + App + Security; complete schemas, golden vectors and SQL design qualification, not a future PASS. Sources v0.2:156–203; annex:324–353,480–545 | Fingerprint module, A020A admin digest, A023A helpers/S024, tests; D08 |
| R07 RESTRICT and inactive deny-first; approved archival principles | Exact retention period/clock, external hold/clearance, admin versions, deletion/redaction obligations and session/Auth partial-failure protocol. Default keep inactive binding, no implicit purge/reactivation | Retention + Identity + Database + App; accepted retention/hold/session policy and ownership. Sources v0.2:205–226; annex:355–478; B1:83–100 | S020 FK/status, administration/retention models, login/context/orchestration; D05/D06/D07/D09 |
| R09 scoped reads/immutable receipts | Current summary/payload/history projections, denied-read behavior, successful write/failed snapshot, G09 consumer disposition. Default immutable receipt separate from optional current snapshot | App + Identity + Database + Domain/G09 owner; projection/receipt/consumer evidence. Sources v0.2:228–242; annex:547–577; adapter:60–79,116–122 | A023A read RPCs, adapter/models/service, G09 reconciliation; D10/D11 |
| R08 LAST provisional 29-step architecture | Freeze final exact object/file/signature/constraint/trigger/dependency graph after all substantive decisions; accepted implementation/test/evidence/stop scope and separate release authority | Database + App + Independent Certification + PO; accepted contract references and exact allowlist, not a target step count. Sources B1:110–235; annex:579–650 | Whole successor/app/test/support inventory; D12, dependent on D01–D11 |

## 5. Implementation scope reconciliation — proposed ownership, not acceptance

### S020 versus A020A identity objects

The following allocation makes creator versus enforcer explicit. It is PROPOSED and remains D02/D12 OPEN. No objects/files are created, and dependencies are not technically accepted by listing them here.

| Identity object / obligation | Proposed creating artifact | Proposed enforcing/using artifact | Dependency / review qualification |
|---|---|---|---|
| public.users membership_status and membership_revision | Derived S020 | S020 UID policies/helper/final FG002; A020A profile administration | Exact active/default/inactive transition policy and legacy row treatment D01/D09 |
| Named replacement Auth FK, existing UID partial uniqueness, status/revision CHECKs | Derived S020 | Database constraints; A020A controlled bind/unbind | Existing exact FK name/definition must be established; stop on drift, no guessed duplicate constraint |
| public.g08_identity_administrators | Derived S020 | A020A admin authorization/lifecycle guards | Subject RESTRICT FK, PK, interval/revision CHECKs in S020; overlap/current/last-root guard algorithm A020A; root trust OPEN |
| public.g08_identity_events | Derived S020 | A020A controlled inserts and history protection | PK/action/revision/digest/object CHECKs S020; immutable UPDATE/DELETE trigger attachment A020A |
| public.g08_administration_receipts | Derived S020 | A020A identity path; later A023A authority/retention/hold paths | PK, namespace/scope/action/key uniqueness and typed digest/result CHECKs S020; canonical field/replay/PII retention policy D05/D08 |
| Foundational RLS and direct profile/new-table privilege restrictions | Derived S020 in same transaction as foundation tables | A020A/A023A exact owner-function/admin RPC grants | No ordinary profile INSERT/UPDATE/DELETE between steps; no application traffic while administration functions unavailable |
| public.g08_deny_history_mutation() | NEW A020A | Identity/history triggers there; later A023A version/hold/event triggers reuse | Owner/invoker/search_path/EXECUTE and trigger-safe behavior reviewed D03 |
| public.g08_guard_profile_write(), public.g08_guard_identity_admin_write() and identity trigger attachments | NEW A020A | Profile/admin write paths | Constraint versus guarded invariants enumerated; no caller-set GUC or general trusted JSON flag; exact algorithms OPEN |
| public.g08_administer_profile(p_request jsonb) and g08_set_membership_status(...) | NEW A020A | User-scoped identity-admin RPC clients | Depends only on S020 identity tables and private digest; no unavailable A023A reference |
| public.g08_administration_digest(p_value jsonb) and receipt replay | NEW A020A | Identity/admin mutation canonicalization and later shared admin namespaces | Does not depend on later data_fabric hash helper; accepted canonical specification shared, implementation qualified independently |
| Public identity history indexes, scoped lookup/overlap support | Derived S020 for accepted table indexes; A020A for guarded absence/overlap checks | Identity-admin reads/locks | Exact names/keys and null/revocation interval semantics must be frozen, not left to implementer discretion |
| Deferred authority version/event and retention issuance/event FKs | NEW A023A, NOT S020/A020A | A023A atomic version/event writes | Distinct from nondeferrable Auth FK; no weakening of deletion restriction |
| Assignment/cycle/audit/retention objects, guards, helper/read/admin RPCs | NEW A023A after S023+A020A | Derived S024 business lifecycle; scoped read clients | All new data_fabric objects/constraints/triggers belong in accepted A023A object annex; no forward-reference creation in A020A |

S020 final FG002 can require current membership status without later stewardship authority. A020A disabling membership denies use immediately; revoking stewardship lineage in a combined runtime workflow is a later orchestration concern after A023A exists. If accepted admin authorization instead depends on later authority tables, this proposed split must change before B2. Migration quiescence is mandatory, not an excuse for unreviewed dependency errors.

The exact creator of each additional index/constraint/trigger and function overload must appear in the frozen object inventory; the table above does not invent missing names or algorithms. Existing source specifications/annex remain unchanged even where this proposal clarifies or differs from them.

### Retention-administrator historical reconstruction

ESTABLISHED: annex:370–470 proposes a mutable administrator row, administrator_id/revision snapshots in holds/authorizations and immutable administration receipts. It does not establish an accepted retention-administrator lifecycle/version writer. Revision numbers alone cannot reconstruct omitted historical fields.

| OPEN option D07 | Required proof / scope effect |
|---|---|
| Dedicated immutable retention administrator versions — RECOMMENDED | Each grant/change/revoke appends full scoped subject/interval/revision/parent-or-bootstrap evidence; hold/authorization events reference exact administrator version; constraints prevent missing or ambiguous history. Adds explicit version table, writer/guards/FKs/tests to A023A if accepted |
| Receipts as authoritative versions | Require complete immutable before/after administrator snapshots, stable typed action schema and (administrator_id,revision) uniqueness/reference guarantees; no reliance on an arbitrary result JSON projection. Exact lookup, integrity and retention proof required |

Both options remain OPEN. Recommendation of a version table is not a selection. Database+Identity/Security+Data/Retention must decide version validity, expiry/revocation semantics and retention obligations; record creator artifacts and schema expansion before R08 freeze. Do not silently use current mutable administrator rows to authorize old history.

### Provisioning treatment D11 — OPEN

Observed: scripts/provision_production_tenant.py:41–67 directly inserts profiles and binds Auth UUID by email; :70–76 uses a service-role/Auth admin composition. services/production_tenant_provisioning_service.py:196–203,238–272 calls profile creation, invitation and binding. These are incompatible with proposed protected writes. Local stub/database users and dynamic/external consumers must not be conflated with verified hosted coverage (annex:547–577).

Recommend controlled-administration refactor of BOTH script adapter and service, with accepted verified-identity binding evidence and explicit partial-failure/receipt behavior. Alternative: verifiably disable the consumer, identify activation controls/owner and preserve a documented no-use contract. The choice is OPEN; the file allowlist is not expanded or frozen here. No indefinite silent disable, grandfathered direct write or email-based automatic ownership inference is accepted by Codex.

### Provisional graph and immutable originals

Retain the 29-position proposal: S001–S020; A020A; S021–S023; A023A; S024–S027. Four derived originals are S011/S013/S020/S024. Two new proposed SQL artifacts are 020a_g08_identity_administration.sql and 023a_g08_stewardship_authority.sql. Twenty-three unchanged parent artifacts are S001–S010, S012, S014–S019, S021–S023 and S025–S027. Full filenames/positions remain in B1:114–150 and annex:583–615; no successor artifacts exist from this task.

New retention versions or guard objects might fit A023A but still expand its accepted object inventory. Bootstrap/admin/deprovisioning tools, live-session validators, external hold integrations or provisioning refactors may require more files/artifacts. Do not silently include them or treat 29 as frozen. R08 resolves LAST after D01–D11 and actual scope acceptance.

CLOSE-014's original 27 files/manifests/seal and CLOSE-015 historical evidence remain immutable. Parent seal remains c09bf47ff8c5dc5dcb8307569ee0180319fb904d1128610483e782ff4fc31500. Preserve S025 confirmed-write denial; no G09 grant or canonical-write enablement is bundled. Quiescence spans app/API/workers/schedulers/managed jobs/direct RPC callers from first migration statement through actual authorized acceptance, including intermediate email-based definitions. No working quiescence control or hosted connectivity is claimed.

## 6. Distinct OPEN decision blockers — canonical count = 12

Counting rule: count each canonical decision package below ONCE, irrespective of how many R rows, components or criteria reference it. Conditions/evidence and missing signatures for the same decision are not extra copies. Policy-principle approvals P01–P07 are not unresolved blockers. These are unresolved decisions, not a count of missing test cases or individual columns. R08 integration is a distinct final scope/release decision, not a second count of its upstream contracts.

| Blocker | Distinct unresolved decision | R mapping | Responsible reviewer function | B1 B2-entry criteria | Status |
|---|---|---|---|---|---|
| D01 | Final typed FG002 fields/defaults/limits/identity/status/alias/merge contract | R01 | Application + Database + Identity | B2-03 | OPEN |
| D02 | Identity/root administration, bootstrap/succession/last-root/trusted-write guard and global lock protocol | R03 | Database + Identity/Security + Application; Domain for scoped root | B2-05 | OPEN |
| D03 | Exact SECURITY DEFINER ownership/effective privileges/helper/API exposure and SERVICE-01 replacement | R02/R03 | Database + Identity/Security + Application; PO disposition | B2-04 | OPEN |
| D04 | Historical assignment/parent expiry/material-change/held-review and replacement lifecycle evidence under approved SoD | R04/R05 | Domain + Database + Identity/Security | B2-06 | OPEN |
| D05 | Exact retention period/start clock/policy-version/redaction/deletion obligations and canonical-request retention | R05/R07 | Data/Retention + Identity/Security + Database; PO conflicts | B2-07 | OPEN |
| D06 | Authoritative external/legal-hold integration, freshness/clearance standards, relied-upon event set and issuance/revoke/hold concurrency predicate | R05/R07 | Data/Retention + Identity/Security + Database | B2-07 | OPEN |
| D07 | Retention-administrator history representation and version-bound authority/expiry reconstruction | R03/R07 | Database + Identity/Security + Data/Retention | B2-05/B2-06/B2-07 | OPEN |
| D08 | Complete business/admin canonicalization, digest/receipt/replay/legacy interoperability contract | R03/R06 | Database + Application + Identity/Security | B2-08 | OPEN |
| D09 | Current session/membership assurance and Auth/DB partial-deprovisioning protocol/ownership | R02/R07 | Identity/Security + Application + Database | B2-07/B2-04 | OPEN |
| D10 | Scoped reader projections/historical receipt/outcome semantics and G09 actual consumer disposition | R09 | Application + Database + Identity/Security + Domain/G09 | B2-09 | OPEN |
| D11 | Operational provisioning consumer refactor-versus-verifiably-disabled treatment | R03/R07/R09 | Application + Identity/Security + Database | B2-09 | OPEN |
| D12 | Final integrated object/file/dependency/acceptance/stop allowlist and separately bounded implementation release | R08 LAST | Database + Application + Independent Certification + PO | B2-10/B2-11/B2-12 | OPEN |

Total distinct unresolved decisions: **12**. Actual reviewer dispositions (B2-02) are required evidence for these decisions collectively and not counted again as a thirteenth copy. The separate B2 authorization remains absent and is included in D12's release boundary; none of these decision entries grants it. Named reviewers/appointments remain unassigned. Any newly discovered independent issue gets its own ID and revised count under separate authorized documentation scope; no count reduction through regrouping or recommendation alone.

## 7. Gate B2 entry checklist — B1 identifiers preserved

| Criterion | B1 requirement and effect of PO policy closure | Current readiness |
|---|---|---|
| B2-01 | Distinguish reported PO directions/B1 scope from technical sign-off; add P02–P07 policy closure | MET FOR PLANNING RECORD ONLY; no technical release |
| B2-02 | Actual reviewer identity/function/date/version/hash/evidence/rationale/conditions for R01–R07/R09 | NOT MET; no independent technical dispositions supplied |
| B2-03 | Complete typed field/default/null/alias/merge/direct-RPC truth tables | OPEN D01; PO direction does not supply field contracts |
| B2-04 | Exact owner/schema/overload/helper/table ACL/RLS/bypass and SERVICE-01 design accepted | OPEN D03/D09 |
| B2-05 | Root/bootstrap/succession/last-root/recovery/admin guards and locks accepted | OPEN D02/D07 |
| B2-06 | Assignment/version/cycle/event/parent/expiry/held semantics and SoD enforcement accepted | OPEN D04/D07; pairwise/clearance UID principles closed only at PO level |
| B2-07 | Accepted exact retention/hold/issuer/clearer/expiry/RESTRICT/deletion/session contract | OPEN D05/D06/D07/D09; fail-closed, SoD, immutable evidence/revalidation/no-delete principles approved |
| B2-08 | Business/admin schemas/serialization/digest dependency/vectors/compatibility accepted | OPEN D08; reference examples exist, no interoperability acceptance inferred |
| B2-09 | Reader projection/receipts/G09 and provisioning/legacy consumer treatment accepted | OPEN D10/D11 |
| B2-10 | Exact future directory/file/object/signature inventory and graph frozen by actual reviewers | OPEN D12; provisional 29 not frozen |
| B2-11 | Bounded implementation criteria/future isolated tests/byte/evidence/unknown-commit stop rules accepted | OPEN D12; no future test PASS demanded before implementation authorization |
| B2-12 | Separate explicit B2 instruction naming accepted versions/hashes, final allowlist/location/permitted changes/exclusions/stops | NOT MET; current task is documentation only, D12 |

Gate B2 entry is **NOT READY**. One criterion is met only for planning; eleven remain OPEN or NOT MET. These criteria are not summed with the 12 distinct decision blockers: they are a many-to-many checklist. Completing this register cannot mark technical criteria MET.

## 8. Blank reviewer disposition template

Use a separate actually authorized review record; do not overwrite source documents or infer a filled signature from circulation. All fields below are intentionally blank and no decision is preselected.

| Required field | Reviewer completion |
|---|---|
| Register ID / R ID / blocker ID | |
| Reviewer identity | |
| Reviewer function / accountable authority | |
| Review date / timezone | |
| Exact document filename and version | |
| Exact SHA-256 examined | |
| Contract clause / implementation item reviewed | |
| Decision — ACCEPT / REJECT / CONDITIONALLY ACCEPT (select one) | |
| Evidence examined and source references | |
| Rationale / selected exact option | |
| Conditions / required evidence / due gate | |
| Condition owner | |
| Conflicting dispositions requiring reconciliation | |
| Implementation item released or blocked; precise scope | |
| Independent signature/attestation reference, if required | |

Conditional acceptance cannot leave an implementation-determining contract unspecified and release its code anyway. A reviewer may accept policy/design now with named later hosted evidence conditions only when the implementation contract itself is complete. Candidate certification/sign-off remains a later gate and must bind exact frozen bytes; nothing here is a certification claim.

## 9. Stop rules, circulation and completion boundary

Stop without writing on any authoritative source hash mismatch; all four matched for this task. Stop before executable work if any relevant D01–D12 decision lacks accepted exact scope, the final file/dependency inventory is absent, an unresolved conflict remains, or a separate bounded B2 instruction has not been issued. PO policy closure alone does not override those stops.

No executable SQL, application edits, tests, Git operations, PostgreSQL/database connections, Supabase/hosted operations, credential access/changes, migrations, deployments, reviewer impersonation, successor creation or edits to existing decision records. No bootstrap, account disable/delete, hold clear, grant/revoke or session operation. No staging or production authorization; SU-513239 remains unresolved in working context and unrefreshed.

Future execution must preserve original per-artifact transactions and current-transaction-only rollback. Unknown commit means stop, preserve last definitely committed step/receipt and seek separately authorized read-only reconciliation; no replay-all/down migration/history repair/regrant/cleanup/automatic compensation. Auth partial failure keeps DB membership inactive when committed; successful mutation plus snapshot failure is not a rollback. These are future contract requirements, not operations performed now.

Recommended closure order: D02+D03 first with Database/Identity/Application; D05–D07 with Data/Retention/Identity/Database in parallel where independent; D01/D04/D08/D09/D10/D11 with their owners; then D12/R08 LAST. This is a circulation plan, not reviewer contact or a claim that signatures exist. Controlled-administration provisioning refactor is recommended, not selected. Retention versions, periods, external holds and clearance evidence stay OPEN.

This document is complete as a register of decisions to close. It does not assert those technical decisions closed. Completion response reports exact path, line count, SHA-256, source hash results, before/after change counts, the 12-decision blocker count and NOT READY result. The new file's own digest is kept external to avoid self-reference. Exactly one Markdown creation is authorized; existing CLOSE-014/015/016 artifacts are hash-compared before/after. This does not audit unrelated concurrent workspace activity outside those directories.

**PO POLICY DIRECTIONS APPROVED.**
**GATE A TECHNICAL CLOSURE PENDING.**
**GATE B2 EXECUTABLE IMPLEMENTATION ON HOLD.**
**STAGING EXECUTION NO-GO.**
**PRODUCTION NO-GO.**
