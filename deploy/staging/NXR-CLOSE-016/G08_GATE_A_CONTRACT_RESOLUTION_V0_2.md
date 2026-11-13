# NEXORA CLOSE-016 — G08 Gate A Contract Resolution v0.2

Prepared: 27 October 2026, Asia/Calcutta. Status: PROPOSAL FOR REVIEW; NOT AN APPROVAL.
Gate A PENDING. Implementation UNAUTHORIZED. STAGING EXECUTION NO-GO. PRODUCTION NO-GO.

## Authority, baseline and interpretation

Authorized change: creation of this Markdown file only. This document does not amend v0.1, any decision record, checkpoint, SQL, code or certification. Every recommendation below is PROPOSED, not an accepted policy. UNRESOLVED items require actual reviewers; specifying a recommended option does not select it for execution.

Authoritative source: [G08_GATE_A_DESIGN_V0_1.md](G08_GATE_A_DESIGN_V0_1.md), all 283 lines. Verified source SHA-256: `a092fa13c30721e5857b15ca1d266671394463cbe96ec7175c65f1ee8d149cf8`. Parent execution package remains CLOSE-014, recorded seal `c09bf47ff8c5dc5dcb8307569ee0180319fb904d1128610483e782ff4fc31500`. CLOSE-015 historical results do not certify proposed bytes.

ESTABLISHED = observed repository source or an explicitly historical recorded result. PROPOSED = exact target submitted to review. UNRESOLVED = decision/evidence missing. No hosted state, reviewer identity, tested outcome or deployment caller is invented. Source references are repository-relative; line numbers refer to inspected current sources. Decisions are presented R01–R07, R09, then R08 LAST.

## R01 — Exact FG002 effective-role and mutation contract

ESTABLISHED: `services/cloud_account_registry_service.py:19–24` separates resolve/approve sets; `:215–226` checks single authorization; `:260–289` checks preview resolve permission but not current commit resolve/approve authority. `auth/role_constants.py:17–50,65–71` normalizes many aliases. `supabase/migrations/202610110001_bind_user_profiles_to_auth_uid.sql:223–232,288–303,417–493` uses broad raw resolver roles, authenticated/service-role grants and item-overrides-shared merging without a distinct SQL approval guard. Preview `service.py:271–272` currently applies the opposite precedence.

PROPOSED recommended boundary mapping: trim ASCII whitespace and lowercase the raw profile role, then use this complete table. Do not invoke the general alias map first. Other application features keep their existing normalization. Resolve and approve are separate booleans; denied mutation roles can retain separately defined read access.

| Normalized raw profile value(s) | Effective FG002 role | Resolve | Approve |
|---|---|---|---|
| super_admin; global_admin | super_admin | yes | yes |
| client_admin; organization_admin | client_admin | yes | yes |
| finance | finance | yes | no |
| operations | operations | yes | no |
| executive; cio; security; technical; auditor; viewer; sales_engineer | same named role | no | no |
| admin; administrator; superadmin; customer_admin; customeradmin; customer_owner; org_admin | unsupported administrative alias | no | no |
| ceo; cto; cfo; finops; finopsmanager; leadership; approval; saas; msp; cloudops; cloud_ops; engineering; engineer; governance; sales engineer; solution engineer | unsupported alias | no | no |
| NULL; empty/whitespace; any other value; non-string | invalid | no | no |

This is an intentional proposed narrowing for legacy aliases, not a claim of compatibility. It preserves the selected three approval labels, with organization_admin effective as client_admin, and explicitly retains global_admin as super_admin. Alternative: admit each legacy alias in a reviewed table; no implicit wildcard alias support. Require review of affected stored roles before migration; no automatic role rewrite or reconciliation is authorized.

| Path | Exact proposed rule |
|---|---|
| Single | Current UID-bound active profile, active organization, org=tenant; allowed raw role; confirmed is actual boolean TRUE; nonblank reason; approval role if requested status is APPROVED/ACTIVE, even if other fields are incomplete |
| Preview | Current resolve authority; validate every effective item; reject approval-intent items for nonapprovers; return advisory preview only |
| Commit | Reauthenticate client/context match; re-read membership and raw role in SQL; repeat all preview validation; no preview authority token |
| Effective item | Shared object merged with item object, item wins. Reject unknown keys and nested scope/actor/role fields. Validate payer/account against immutable scoped discovery; reject duplicate account identities in one bulk |
| Direct single/bulk RPC | Same database checks, before writes; single remains guarded when called by bulk; authenticated access never substitutes for approval authority |
| Intermediate S011/S013 | Five total confirmation guards across S011/S013/S020 reject NULL/FALSE. Same effective approval table and approval-intent rule wherever resolver bodies occur; intermediate email identity remains quarantined |

Define allowed mapping keys as the existing `RESOLUTION_FIELDS` list (`services/cloud_account_registry_service.py:34` onward) plus its explicitly copied discovery-evidence fields (`:238–247`); freeze their enumerated names and types before Gate B. Item-only identity/control keys are payer_account_id, account_id, expected_state. Unknowns deny; identity/control fields are removed from mapping after validation. Expected state is explicitly validated, not accepted as an arbitrary bypass of stale-state protection. SQL and application use the same case/whitespace normalization for status and account identity. Entire bulk transaction rolls back on any item rejection.

UNRESOLVED: approve the bounded table versus explicit legacy expansion; exact mapping-field/type enumeration and status normalization; empty/duplicate bulk handling limits; service-role EXECUTE removal versus retained ineffective legacy grant. Recommendation: revoke human FG002 business execution from service_role, retain authenticated only, and reject missing auth.uid(). Reviewers: Database, Identity/Security, Application, PO. Blocking evidence: raw-role truth table, typed request list and merged-item examples; no future runtime result needed for Gate A.

## R02 — Authenticated-user stewardship wire and privilege contract

ESTABLISHED: certified S024 `deploy/staging/NXR-CLOSE-014/sql/024_0020_create_stewardship_rpcs.sql:18–24,42–48,67–70` trusts supplied authority and grants service_role. `utils/auth.py:60–135` creates/stores session-local auth_client. `auth/authenticated_tenant.py:86–134` uses stored profile identity; it is not a current membership query. `canonical_stewardship/supabase_repository.py:20–60,81–116` builds the old envelope. `G08_DECISION_SHEET.md:126–136` preserves server-only disposition and broader hold.

PROPOSED A (recommended): server dispatches using the session-local nonprivileged user client. SQL derives actor solely from auth.uid(), verifies active UID-bound membership, active organization, canonical org=tenant and supported domain, then current assignment authority. B remains a verifiable bounded capability design requiring a replacement specification. No unsigned subject envelope or service-key fallback.

Exact business signatures remain `data_fabric.stewardship_create_review(p_request jsonb) returns jsonb` and `data_fabric.stewardship_transition_review(p_request jsonb) returns jsonb`. One strict v2 wire is defined in R06; SQL validates object type, all required/unknown keys, primitive/nested types, UUID canonical form, limits and mutation semantics. Direct authenticated callers face the same validation. Caller authorization/state/role/subject fields are rejected. Legacy permission-array validation is exercised only against historical behavior in isolated regression fixtures; there is no production compatibility authority route.

| Object category | Effective privilege proposal |
|---|---|
| Business/read RPCs | Explicit EXECUTE to authenticated only; revoke PUBLIC/anon/service_role; validate inherited/default privileges and exact overloads |
| Schemas | authenticated USAGE on the required data_fabric schema only, no CREATE; public schema existing USAGE retained. Exposed API schema decision separately reviewed |
| Private helper functions | No direct EXECUTE to PUBLIC/anon/authenticated/service_role; callable only by controlled owner through definer bodies |
| Authority/cycle/audit/identity tables | Revoke all ordinary direct DML/DDL, including service_role; no blanket table SELECT. RLS enabled as defense in depth, not owner protection |
| Profile table | Existing scoped authenticated SELECT retained with active-status policy; protected writes only via R03 identity administration; no ordinary INSERT/UPDATE/DELETE |
| Administration RPCs | authenticated EXECUTE only where each function checks dedicated database identity-admin or scoped root authority; never a generic business permission |
| Owners | Explicit reviewed owner, qualified relations/functions, pinned pg_catalog/trusted schemas; no writable schema resolution. Owner/BYPASSRLS administrative compromise remains outside caller guarantee |

Session construction: require Supabase backend, auth_client, live authenticated user matching context.user_id and canonical profile scope; query current membership using that user client before dispatch; SQL rechecks at execution. Do not attach a JWT to a process-global client. No plaintext token, secret, refresh or account operations are part of this document.

Additional source fact: `data_fabric/adapters/supabase/config.py:14–26` requires service_role_key; `client.py:30–49` creates a service-role client when raw_client is absent. Recommendation: add a small stewardship-specific injected user-client wrapper/protocol, never construct this service-role configuration for human requests. Existing generic Data Fabric adapter remains untouched.

UNRESOLVED: actual selection A/B; owner/admin role identities; exact schema exposure and session freshness policy; explicit reconciliation of SERVICE-01 and checkpoint `EXECUTION_CHECKPOINT.md:659–662`. Recommendation A changes these contracts for scoped human RPCs, not for all privileged services. Reviewers: Database, Identity/Security, Application, PO. Gate A needs the privilege/signature/request table and changed-disposition recommendation; hosted JWT/ACL/API proof remains Gate E.

## R03 — Authoritative profile, assignment and root administration

ESTABLISHED: baseline S001 `sql/001_public_prerequisites.sql:35–42,137–145` has profiles and service-role CRUD; S020 `:6–19` adds UID binding. Existing policy JSON (`migrations/data_fabric/0019_create_stewardship_persistence.sql:2–12`) is not a typed principal/delegation authority model. Review/audit scope is text (`:14–36`).

PROPOSED schema additions (names are proposed allowlist, not created objects):

| Object | Required keys, types and invariants |
|---|---|
| public.users additions | membership_status text active/inactive NOT NULL; membership_revision bigint >=1 NOT NULL; auth binding remains nullable/unique. Active default is new policy, not preservation of a preexisting status |
| public.g08_identity_events | UUID PK; profile ID, old/new UID and org snapshots; authenticated actor UUID; action/reason; old/new revision; timestamp; immutable. Actor snapshots retained without deletion cascade |
| public.g08_identity_administrators | UUID PK, subject_auth_uid UUID RESTRICT FK, validity interval, revoked_at, revision; separately controlled global identity role, not inferred from stewardship/FG002 role |
| data_fabric.stewardship_authority_assignments | UUID PK; org/tenant canonical UUID text; subject_auth_uid UUID RESTRICT FK; domain enum technology/applications; role enum platform_owner/domain_steward/technical_steward/governance_approver; parent ID nullable; valid interval; current revision/revocation |
| data_fabric.stewardship_authority_versions | PK(assignment_id,revision); immutable complete assignment snapshot, grant/revoke actor/reason/event/time, parent ID/revision provenance; no destructive updates |
| data_fabric.stewardship_authority_events | UUID PK; scoped assignment/version/action; authenticated actor; reason/time; immutable history |
| data_fabric.stewardship_review_cycles | UUID PK; unique scoped review ID, cycle_number=1; scoped submission/approval/promotion event references, immutable actor UUID/digest/version snapshots |

Use canonical UUID strings in stewardship scope columns to match existing text composite review keys without altering S023 types. Scope text must equal UUID round-trip canonical output and org=tenant. Membership checks bind to public.users.org_id UUID by validated conversion. All event references use review/org/tenant plus event identity; no unscoped cross-tenant FK. Where a new composite FK needs an additional unique key on existing audit events, add that key in the new artifact explicitly. Assignment parent must share scope/domain, hold platform_owner role, contain child validity and not itself be delegated. Child roles are domain_steward/technical_steward/governance_approver; parent depth zero, child depth one. Domain Stewards cannot delegate in v2.

No overlapping active-effective intervals for the same principal/scope/domain/role. Unique/exclusion or lock-backed enforcement must handle concurrent grants; a check-then-insert alone is insufficient. Assignments are never deleted; revocation increments revision and appends version/event atomically. Changing domain, subject or parent creates a new assignment, not an identity-changing update. Lock-held current parent validity is checked on each new protected operation, not only at grant time.

Exact proposed callable signatures, all returning JSONB receipts:

| Function | Inputs and authority |
|---|---|
| public.g08_administer_profile(p_request jsonb) | strict action create/update_status/update_role/update_org/unbind; profile_id, expected_revision (null only for create), subject_auth_uid, organization_id as applicable, new values, reason, idempotency_key, correlation_id; current identity-admin record required |
| public.g08_set_membership_status(p_profile_id uuid,p_expected_revision bigint,p_status text,p_reason text,p_idempotency_key text,p_correlation_id text) | identity-admin; same revision/event path as administer_profile, no alternate bypass |
| data_fabric.g08_administer_authority(p_request jsonb) | action grant/revoke; scope/domain/subject/role/parent, interval, expected revision, reason, idempotency_key, correlation_id; current scoped platform_owner required |
| data_fabric.g08_require_authority(p_actor uuid,p_org text,p_tenant text,p_domain text,p_operation text,p_from_state text,p_to_state text) returns jsonb | private; validates current principal and returns assignment/version evidence; never trusts p_actor from external callers |

The two JSON administration requests require a separate enumerated field/type annex before Gate B; do not implement generic profile patch JSON. Their idempotency must compare a database-derived complete administrative mutation digest under a scoped key; exact key namespace, retention and receipt storage are UNRESOLVED. No business-RPC hash implementation is silently reused with omitted admin fields.

Profile protections: revoke table-level INSERT/UPDATE/DELETE from ordinary authenticated/service_role, not just column grants; account for inherited/default grants and existing definer writers. Reject arbitrary binding/rebinding or UID/org changes except controlled identity-admin functions. Create inactive/unbound by default; binding+activation requires verified identity/membership evidence and accepted reconciliation procedure. Unbind only inactive, with revoked assignments, reconciled holds/dependencies and separately authorized retention evidence; never for circumventing RESTRICT. Ordinary DELETE is forbidden; physical purge excluded from v2. No self-role elevation, self-reactivation or self-binding by an identity administrator. Another authorized administrator is required.

Root bootstrap/succession proposal: first identity administrator and first scoped Platform Owner are inserted only by an explicitly authorized database-owner bootstrap outside business RPCs, with two accountable human reviews and immutable events. No automatic seed from profile role/email. Subsequent scoped root succession uses a separately reviewed owner-controlled bootstrap procedure to create replacement root, verify its independent Auth identity, then revoke old root. No self-renewal and no automatic last-root deletion. If no valid root/admin remains, fail closed and require that owner procedure; no emergency application bypass. Bootstrap execution is excluded from the candidate run and remains separately authorized.

Lock order: canonical organization row (org UUID ascending for identity move), relevant profiles (UUID ascending), root/parent assignments then child assignments (UUID ascending within level), scoped operation+idempotency advisory lock, review row, cycle row, append events. All business/admin functions follow it. Root grants lock the organization to serialize absence/overlap checks; global identity-admin changes take a separately defined global admin lock before organization locks. Refresh current row versions/validity after acquiring locks. A revocation that serializes first denies; an earlier serialized mutation may commit first. Interval expiry must use one documented authorization decision time after locks, not an accidentally stale pre-wait timestamp.

UNRESOLVED: global identity-admin root model versus external dedicated operator; exact admin field annex/digest storage, bootstrap procedure, lock primitive compatibility and interval constraint implementation. Recommendation: typed immutable versions and separate identity administration; no business-role self-enrollment. Reviewers: Database, Identity/Security, Stewardship, Application; PO/Retention for binding evidence. These are Gate A blockers, not implied implementation choices.

## R04 — Immutable cycle evidence, SoD and held reviews

ESTABLISHED: S024 `:55–62` has scoped state/revision updates but no cycle/SoD. S023 `sql/023_0019_create_stewardship_persistence.sql:48–79` has append-only events/revision checks but no assignment versions/cycle evidence. WP-005 `docs/program_g/WP_005_ACTIVATION_SPECIFICATION.md:184–210` does not prescribe two/three people.

PROPOSED: one cycle created atomically with discovered review. Add explicit audit columns actor_auth_uid UUID, cycle_id UUID, assignment_id UUID, assignment_revision bigint, parent_assignment_id/revision when applicable, fingerprint_version text, mutation_sha256 text, submitted_payload_sha256 text, prerequisite_event_id UUID. Preserve existing text actor as the same canonical actor UUID for compatibility. Each successful mutation increments review revision once and writes exactly one immutable event plus its cycle reference in one transaction. No caller-supplied cycle/evidence actor overrides.

Submission is classified→under_review event; snapshot exact immutable submitted review payload digest and submission assignment version. Approval under_review→steward_approved references that event/digest. Promotion steward_approved→canonical references approval event and same submitted digest. Enforce referential state/type/review/scope consistency in the controlled write path plus applicable constraints. Cycles cannot be rewritten to another event; record a subsequent event to invalidate a prerequisite, never edit historical approval. Audit/version tables reject ordinary UPDATE/DELETE; cycle writes are owner-function-only, with allowed null→event reference transitions enforced.

Recommended pairwise SoD: approver Auth UUID != submitter; promoter != approver. Promoter may equal submitter. Alternative three-person policy adds promoter != submitter. Delegation preserves actual acting human UUID; two roles or two assignments held by one human are not two people. Separate Auth accounts belonging to one human remain an identity-governance limitation requiring reviewer policy; UUID inequality alone does not prove distinct natural persons.

For promotion, submission and approval assignment identities must still be active and their recorded authority must not have been revoked/expired or materially narrowed; inspect immutable versions and current lineage. Revocation+new assignment does not restore old approval. Deny promotion and emit no successful mutation; leave review in its prior state, flagged as held by a derived authority-validity view/read field, not a new unreviewed lifecycle state. Rejection by an authorized Domain Steward remains possible where R05 allows. No reapproval/reopen endpoint, no cycle 2, no silent resubmission.

For replay, use original receipt edge and prerequisite identities; current role must still authorize that edge. Revocation denies replay through business RPC even if original mutation committed. Separate historical read rights may permit an already committed receipt. Do not compare mutable current revision to old expected_revision on an otherwise valid replay.

UNRESOLVED: pairwise versus three natural persons; exact meaning of materially narrowed assignment and expiry's effect on earlier approvals; whether permanent hold is acceptable for canonical work; legacy cycle attribution cannot be invented. Recommendation pairwise and no approval resurrection, with explicit fail-closed holds. Reviewers: Stewardship, Identity/Security, Database, PO. Required evidence: actor/event examples, constraint/atomicity design and before/after revocation scenarios.

## R05 — Complete lifecycle and hierarchy

ESTABLISHED: S024 `:58–62` implements the state edges below without role differentiation. WP-005 `:184–210` says higher authority overrides lower authority, domain stewards approve domain decisions and automation does not override humans; `:217–225` requires a secured canonical-write boundary.

PROPOSED role symbols: T=Technical Steward, D=Domain Steward, P=scoped Platform Owner, G=explicit delegated governance_approver. Each must have active same-domain assignment and membership. Proposed hierarchy reconciliation: P may perform T/D actions by explicitly documented authority inheritance; G inherits only promotion, never general stewardship or administration. This revises v0.1's no-implicit-inheritance recommendation and needs explicit review. SoD is never overridden by hierarchy. Automation has no human approval/promotion authority.

| Operation / edge | T | D | P | G | Additional condition |
|---|---|---|---|---|---|
| create→discovered | yes | yes | yes | no | cycle=1, initial revision=1 |
| discovered→classified | yes | yes | yes | no | reason/evidence |
| classified→under_review | yes | yes | yes | no | durable submitter and payload digest |
| under_review→steward_approved | no | yes | yes | no | actor != submitter |
| steward_approved→canonical | no | no | yes | yes | actor != approver; prerequisite valid |
| canonical→superseded | no | yes | yes | no | replacement review reference |
| superseded→archived | no | yes | yes | no | accepted retention eligibility |
| discovered→rejected | no | yes | yes | no | nonblank reason |
| classified→rejected | no | yes | yes | no | nonblank reason |
| under_review→rejected | no | yes | yes | no | nonblank reason |
| steward_approved→rejected | no | yes | yes | no | retain invalidated approval history |
| All other edges; self-loops; reopen | no | no | no | no | reject without mutation |

Archived/rejected terminal; canonical→rejected, superseded→rejected and any reverse/skip edge forbidden. Multiple effective roles authorize only if one applicable assignment suffices; conflict with an explicit domain restriction fails closed, not majority voting. Define such restrictions before adding them; none are invented here.

Replacement reference: replacement_review_id canonical UUID, different review, same org/tenant/domain/review_type/subject_type/subject_id; replacement state canonical at serialization time. Lock both review IDs ascending; no self/cyclic supersession links. This is a proposed strict same-subject policy; cross-subject replacements need a different accepted contract. Persist the reference and its observed revision in the immutable supersession event, not a mutable JSON label.

Archive eligibility: require a database-held, immutable retention authorization record for the exact review ID and supersession event, with not_before, expiry, hold-clearance, policy_version and Data/Retention authorizing identity. New `data_fabric.stewardship_retention_authorizations` is needed; no caller boolean eligibility flag. An accepted retention-admin role and issuance function are prerequisites (R07/R08). Holds/revocation deny archive; archive never deletes review/audit data.

Canonical is review-state-only. No canonical entity mutation, S025 confirmation, authority verifier or inferred source-of-truth promotion is implemented. A later real canonical write needs a separately accepted secured atomic integration and new scope.

UNRESOLVED: explicit P inheritance versus separately assigned T/D roles; rejection policy; replacement same-subject rule; retention authorizer/record design. Recommend the table with inherited P actions, strict replacement and DB-held eligibility. Reviewers: Stewardship, Database, Data/Retention, Identity/Security, PO. No hierarchy or retention policy is accepted by this recommendation.

## R06 — Exact v2 wire, canonical representation and digest

ESTABLISHED: adapter `canonical_stewardship/supabase_repository.py:37–58,99–115` forwards a create hash and computes a partial transition hash. S024 `:25–29,49–53` compares caller strings; `canonical_stewardship/models.py:68–85` permits arbitrary payload mappings. v0.1 `:166–168` duplicated evidence_references. Proposed numeric limits below are restrictions, not existing compatibility guarantees.

PROPOSED version identifiers: wire_version=`nxr-stewardship-wire-v2`; fingerprint_version=`nxr-stewardship-mutation-v2`. Unknown/missing versions reject. Both RPCs accept only p_request JSON object. No authorization/actor/permissions/cycle/server-result fields. All keys below required; explicit null allowed only where stated. Unknown keys reject recursively for typed objects; arbitrary payload object keys are allowed subject to value rules. SQL independently validates parsed JSONB even for direct RPC.

| Wire key | Create | Transition |
|---|---|---|
| wire_version; fingerprint_version | exact literals | exact literals |
| organization_id; tenant_id | canonical lowercase UUID strings, equal | same |
| review_id | canonical UUID, generated once by server and reused on retry | existing scoped UUID |
| idempotency_key | 1–128 ASCII characters [A-Za-z0-9._:-] | same |
| correlation_id | canonical UUID, retained from first success | same; transport-only |
| expected_revision | null | JSON integer 1..2147483646 |
| target_state | discovered | allowed state string |
| review_item | object described below | null |
| rationale | nonblank string, 1–4096 UTF-8 bytes | same |
| evidence_references | ONLY source: ordered unique array of 0..64 strings, each 1..2048 UTF-8 bytes | same |
| replacement_review_id | null | canonical UUID for superseded only, otherwise null |
| retention_authorization_id | null | canonical UUID for archived only, otherwise null |
| payload_hash | lowercase 64-character SHA-256 hex | same |

Create review_item exact keys: review_key (1–256 UTF-8 bytes), review_type identity/quality, domain technology/applications, subject_type and subject_id (each 1–256 UTF-8 bytes), assigned_role (null in v2; no assignment by this field), payload (JSON object). Nested scope/review_id/evidence_references are rejected; scope/review ID/evidence occur only at top level. This removes the nested-scope ambiguity rather than accepting mismatched duplicates. Missing required field != null != empty; missing rejects. Empty payload {}, evidence [] accepted; empty rationale/identifiers rejected. No trimming changes stored/hash-bound strings; whitespace-only required human text rejects.

Payload supports objects, arrays, strings, booleans and null; rejects all numeric values recursively. expected_revision is the only numeric wire field. Arbitrary precision decimal values must be explicitly defined domain strings; no automatic number→string conversion. Maximum payload serialized canonical bytes 65536; maximum request canonical bytes 131072; nesting depth 16; 256 keys per object; 256 elements per payload array. Reject overlimits in app and DB. Domain must confirm these restrictions; no old payload is rewritten.

String domain: valid Unicode scalar values representable in the accepted database UTF-8 text domain; reject U+0000 and unpaired surrogates. No Unicode normalization; composed/decomposed text hashes differently. Canonical JSON: recursively sort object keys by Unicode scalar value, preserve array order; encode UTF-8 without BOM; no insignificant spaces; quote strings with JSON double quotes, escape quote/backslash, encode U+0001–001F as lowercase `\u00xx`, otherwise emit scalar unchanged; booleans/null lowercase. expected_revision rendered decimal without leading zero; reject noninteger or alternate exponent notation at server parsing, and enforce integer value semantics at JSONB boundary. Raw duplicate object keys reject at server parser; direct JSONB path is explicitly defined by already-parsed JSONB semantics, not a false guarantee of reconstructing discarded duplicates.

Canonical mutation object contains exactly: version=fingerprint_version; operation=create_review/transition_review (derived from RPC); actor_auth_uid (database-derived); organization_id; tenant_id; review_id; idempotency_key; expected_revision; target_state; review_item; rationale; evidence_references; replacement_review_id; retention_authorization_id. All present with the wire null rules. Exclude wire_version (indirectly pinned by fingerprint_version mapping), correlation_id, payload_hash, credentials, timestamps, generated event IDs, resulting revision and current assignment revisions. Persist assignment versions and observed replacement/retention evidence separately. Server-owned effects must not accept hidden caller inputs. Version any added mutation input.

DB builds that object from validated request plus auth.uid(), computes SHA-256 bytes, encodes lowercase hex and compares exactly to payload_hash BEFORE replay response or mutation. Client hash is not authentication and need not be trusted as server-originated. Proposed implementation is qualified `pg_catalog.sha256(pg_catalog.convert_to(canonical_text,'UTF8'))` with hex encoding, subject to Database reviewer validation for the selected PG17 baseline; no pgcrypto installation is presumed. If unsupported on the accepted target, return to design review; do not silently add an extension. Helper signatures: `data_fabric.g08_canonical_mutation(p_value jsonb) returns text`; `data_fabric.g08_mutation_digest(p_value jsonb) returns text`, private EXECUTE only.

Replay key=(org,tenant,operation,idempotency_key), retaining original operation names review_created/state_transition for storage compatibility. Different actor changes digest and conflicts; different version/request conflicts. Same key/digest plus current applicable authority returns original immutable receipt even after later transitions. Review/current-state checks for a NEW operation remain after replay lookup; replay authorization reads original event/cycle, not merely current state. Membership/authority locks serialize with revocation; supersession locks both reviews in sorted order before key lookup/write. Review R03 order explicitly for multi-review operations. No automatic retry of ambiguous commits.

Legacy: no live legacy envelope acceptance. Preserve original package/test evidence; reject unsupported versions. Before later deployment, inventory any existing stewardship records/keys. If present, stop for an accepted receipt/version/cycle compatibility plan; no fabricated historical actors/cycles. No legacy migration or payload conversion is authorized here.

Proposed golden serializer/digest vectors (literal canonical bytes, no trailing newline). Reference digests below were calculated by in-memory SHA-256 only during documentation preparation, not by executing candidate/application/SQL tests:

| Canonical UTF-8 text | SHA-256 lowercase hex |
|---|---|
| `{}` | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` |
| `{"a":null,"b":true}` | `777fd7cd7406c9292c68b3a96618c04974c9823714b5625f200e8dc3eb5d6bf0` |
| `{"a":"x","z":["first","second"]}` | `884c876bd4a1fbc1a91fc25b192e319acdba00800b5effe57a9014e3198975a8` |
| `{"control":"\u000a","quote":"\""}` | `cef1089355e9f984335631700e02ed20d8225df81f136194c0afbd94cc8dba80` |

Additional exact serializer cases: input keys z,a → output a,z; scalar keys U+E000 then U+10000 remain in that order; arrays ["b","a"] never sort; U+00E9 differs from U+0065 U+0301; absent rationale rejects, null rationale rejects, [] evidence succeeds, duplicated evidence rejects, payload {"n":1} rejects, revision 1 succeeds, 0/2147483647 rejects. Full mutation vectors must include fixed actor/scope/review UUIDs and each operation, changed-field inequality and transport-only correlation equality; their complete byte strings/digests are a required Gate A annex not yet present. These small serializer vectors alone do not establish full mutation interoperability.

UNRESOLVED: accept numeric/size restrictions and direct-JSONB lexical limitation; exact full-mutation golden annex; built-in digest signature qualification; legacy inventory handling. Recommend v2 single-source evidence and DB recomputation. Reviewers: Database, Application, Identity/Security, Stewardship. Missing full vectors remain a blocker rather than a claimed test PASS.

## R07 — Restricted deletion, deny-first deprovisioning and retention

ESTABLISHED: S020 `:6–19` uses nullable unique CASCADE; `:121–139` helper includes service-role branch and no membership_status. `utils/auth.py:77–135` checks profile at login; context `auth/authenticated_tenant.py:86–134` consumes cached session. `G08_DECISION_SHEET.md:114–118` conditionally accepts CASCADE with no binding/deletion authority. Audit actor snapshots in S011 `:12–27` and stewardship schema `:27–41` do not themselves cascade from profiles.

PROPOSED: named Auth FK ON DELETE RESTRICT NOT DEFERRABLE. Alternative immediate NO ACTION has distinct constraint-check semantics; deferred NO ACTION would allow a different temporary-violation transaction contract and is not recommended. Exact existing constraint name/definition must match accepted baseline; stop on unexpected preexisting FK rather than double-add. This is a replacement proposal needing Data/Retention/Database/PO disposition, not an amendment to UID-01 by documentation.

Deny-first sequence: (1) separately authorize account deprovisioning and capture identity/holds; (2) atomically set profile inactive, increment membership revision, revoke active assignment lineage and append identity/authority events in DB; (3) after DB denial is committed, disable sign-in and revoke refresh/sessions through accepted Auth administration; (4) verify denial and retained attribution. No Auth token invalidation claim. A stale token must fail current-active-membership checks on sensitive RPCs. Other services/read policies must be inventoried; this change cannot claim global access revocation while service-role bypass or unmodified consumers remain.

| Partial failure | Required proposed behavior |
|---|---|
| DB denial fails/unknown commit | Do not announce completed deprovisioning; freeze further workflow, reconcile under separate read authority. Emergency Auth suspension only with existing incident authority, not automatic compensating SQL |
| DB denial committed, Auth action fails | Keep membership/assignments inactive; no rollback/reactivation; record pending Auth revocation and named incident owner |
| Auth disabled but DB state uncertain | Keep sign-in disabled; do not restore access; reconcile DB before any further change |
| Verification fails | Keep NO-GO for affected activation; preserve evidence; no auto-retry/purge |

Profile INSERT/binding/role/org/status/UID changes use R03 protected administration; physical DELETE excluded. Unbinding requires inactive profile, revoked assignments and accepted hold/reference reconciliation. It is not a workaround for RESTRICT. Existing assignments' RESTRICT references may intentionally keep Auth identity undeletable even after unbinding; no promise of eventual physical deletion until retention policy chooses disposition.

Session policy recommendation: current authenticated session/user, current active profile/organization and current authority checked per sensitive mutation. Decide whether additionally requiring live session_id validation is necessary; if selected, specify exact source/privilege/cost and expand allowlist. Do not imply local SDK user object proves live session revocation. Never cache authority as sufficient until token expiry.

Retention roles: Data/Retention defines durations, field-level redaction, holds and archive eligibility; Identity/Security owns sign-in/session actions and verified human identity; Database owns enforcement/dependency safety; Application owns per-request status checks; PO resolves conflicts. Proposed new retention administrator assignment is separate from stewardship P and identity-admin. `data_fabric.g08_authorize_retention(p_request jsonb) returns jsonb` requires that accepted admin role, review/supersession IDs, policy version, not_before/expiry, hold-clearance record, reason and idempotency fields. Authorizer identity and hold-clearance evidence cannot be caller booleans. Exact authoritative hold register and retention-admin bootstrap are UNRESOLVED; archive remains unavailable until decided.

UNRESOLVED: durations/redaction/holds, physical deletion obligations versus retained FK references, session assurance level, full sensitive-consumer list, Auth procedure, retention admin/hold model. Recommendation RESTRICT and retained inactive identity until obligations resolved. Hosted dependencies, privileges and real JWT/session behavior unverified. Reviewers: Data/Retention, Identity/Security, Database, Application, PO. No provisioning/deprovisioning/Auth operation is performed.

## R09 — Scoped reads and immutable mutation receipts

ESTABLISHED: adapter `canonical_stewardship/supabase_repository.py:60–79,116–122` reads current row after successful RPC, raises if unavailable and returns current row instead of original receipt. `G09_TECHNICAL_REVIEW.md:7–31` proposes service_role table SELECT after chain, not authenticated reads. `EXECUTION_CHECKPOINT.md:662` retains that route. No existing scoped read RPC is established.

PROPOSED signatures: `data_fabric.g08_read_review(p_organization_id text,p_tenant_id text,p_review_id uuid) returns jsonb`; `data_fabric.g08_read_receipt(p_organization_id text,p_tenant_id text,p_operation text,p_idempotency_key text) returns jsonb`. Both authenticated EXECUTE only, DB-derived current identity/membership, supported scope/domain; no direct table SELECT. Private helpers are not callable as read bypasses.

Current read roles: active same-domain T/D/P/G may read review summary; evidence/payload projection requires D/P or the original submitting actor still holding active T authority. Proposed summary: review_id, org/tenant, review_type, domain, subject_type/id, state, revision, active, held flag/reason code, cycle ID, created/updated timestamps. Never include arbitrary policy config, full assignment records, session data or hidden personal fields. G receives summary and immutable approval references necessary for promotion, not unrestricted payload. Domain must approve this information model; no UI reader is activated here.

Historical receipt: original actor with current membership and at least current same-domain reader authority may retrieve own receipt even if the exact old edge permission was revoked; D/P may audit same-domain receipts. Inactive/unbound users and foreign scope deny. This is intentionally distinct from business-RPC replay, which rechecks current edge authority. No public existence leak: not-found/unauthorized response contract is identical at API boundary; denial audit contains only approved identifiers.

Immutable receipt keys: event_id, review_id, org/tenant, operation, cycle_id, actor_auth_uid, from_state, state (original to_state), resulting_revision, occurred_at, idempotency_key, fingerprint_version, payload_hash, prerequisite event reference. Business response adds replayed boolean as delivery metadata; receipt content remains identical on replay. Database event is source of truth; adapter returns typed MutationReceipt and never replaces it with a current read result. Optional snapshot is a separate field/action explicitly labelled current_revision/current_state.

Post-write read failure: preserve successful receipt and report snapshot unavailable without claiming write rollback. RPC timeout/transport failure with no receipt is outcome_unknown; reconcile with read_receipt or retry same request only under accepted idempotency/authority policy, never generate a new key. If authority revoked after commit, receipt retrieval may deny; operator audit/reconciliation uses separately approved rights.

UNRESOLVED: reader projection and historical rights, denial semantics, G09 supersession versus continuing other service consumers. Recommend replacing this adapter's G09 dependency with scoped reads; do not automatically apply/revoke the old grant, close G09 or alter its records. Required acceptance/checkpoint changes are a later separately authorized documentation delta. Reviewers: Database, Identity/Security, Application, Stewardship/G09 owner. Gate A needs receipt/current-read examples and actual consumer disposition, not a future GRANT PASS.

## R08 LAST — Derived inventory, dependencies and scope limits

ESTABLISHED: parent manifest `deploy/staging/NXR-CLOSE-014/manifest.json:622–681` orders S023→S024→S025. S023 audit/revision structures `sql/023_0019_create_stewardship_persistence.sql:48–79` lack proposed cycle/assignment/version columns. S001 gives profile service CRUD. `EXECUTION_CHECKPOINT.md:644–654` requires quiescence and explicit execution authority. v0.1 `:213–243` provisional five-artifact plan is not frozen sufficient scope.

PROPOSED exact SQL package inventory, expanding from five to SIX changed/new execution artifacts:

| Order / artifact | Allowed objects/delta and prerequisites |
|---|---|
| Derived S011 `sql/011_202608080001_fg002_account_resolution.sql` | Two confirmation guards; exact R01 roles/approval-intent/merged-item validation in intermediate resolver definitions; no unrelated financial redesign |
| Derived S013 `sql/013_202608090002_p42_owner_optional_resolution.sql` | One confirmation guard and same single authorization contract |
| Derived S020 `sql/020_202610110001_bind_user_profiles_to_auth_uid.sql` | Two confirmation guards; final R01 roles; RESTRICT/status/revision; active membership policies/helper; direct profile write revokes; identity tables/constraints. No functions depending on later authority tables |
| NEW A020A `sql/020a_g08_identity_administration.sql` | Identity-admin/profile function definitions and protected identity-event guards after S020; no dependency on later stewardship authority. Set inactive denies immediately; lineage revocation orchestration waits for A023A/runtime controlled workflow |
| NEW A023A `sql/023a_g08_stewardship_authority.sql` | Typed authority versions/events/cycles; retention eligibility records; existing audit column/unique-key additions; admin/read/hash/authority/retention helpers; explicit ACL/RLS/trigger controls. Depends on S023 and A020A |
| Derived S024 `sql/024_0020_create_stewardship_rpcs.sql` | Authenticated strict v2 RPCs, lifecycle/SoD/fingerprint/receipt, scoped locks and grants; depends explicitly on A023A |

Proposed order: S001–S020, A020A, S021–S023, A023A, S024–S027 = 29 execution artifacts. Existing S021 manifest dependency must include A020A/order boundary; S024 dependency must become A023A. New manifest step identifiers must be unambiguous strings; never silently reuse numeric migration history. No Supabase migration filename/history entry is generated here. Constraint/helper placement may expand again if UNRESOLVED admin/session/hold contracts demand it; return to Gate A instead of silently exceeding inventory.

Unchanged byte-identical certified SQL: S001–S010, S012, S014–S019, S021–S023, S025–S027 (23 artifacts). Adding audit columns/keys occurs in A023A, not by editing S023. S025 remains confirmed-write fail-closed. S027 does not bundle G09. All 27 parent artifacts remain present; four derived parent copies plus two new prerequisites. Original migration sources and CLOSE-014/015 remain immutable.

Exact proposed new/altered object inventory beyond original functions: public.users status/revision/FK/policies and protected-write controls; public.g08_identity_events; public.g08_identity_administrators; public.g08_administer_profile; public.g08_set_membership_status; data_fabric.stewardship_authority_assignments; stewardship_authority_versions; stewardship_authority_events; stewardship_review_cycles; stewardship_retention_authorizations; g08_administer_authority; g08_authorize_retention; g08_require_authority; g08_canonical_mutation; g08_mutation_digest; g08_read_review; g08_read_receipt; explicit audit evidence columns/composite unique keys; append-only/protected mutation trigger functions and exact constraints to be named in the required DDL annex. A separate retained-hold/register model, live-session validator or bootstrap runner is NOT quietly included: those missing decisions prevent final exact object freeze.

| Exact proposed application path | Responsibility |
|---|---|
| services/cloud_account_registry_composition.py | Inject verified session-local human client, no shared mutation fallback |
| services/cloud_account_registry_service.py | R01 raw-role table, preview/commit/item precedence, approval and TRUE checks |
| repositories/cloud_account_registry_repository.py | Bound client/context identity; typed strict RPC input and unknown outcome handling |
| auth/authenticated_tenant.py; utils/auth.py; services/enterprise_spend_composition.py | Preserve raw profile role for boundary mapping, current active membership/organization and session-local resolution; do not globally rewrite roles |
| canonical_stewardship/supabase_repository.py | v2 strict requests; typed immutable receipts, scoped reads and no current-row replacement |
| canonical_stewardship/models.py; canonical_stewardship/service.py | MutationReceipt/current projection types, explicit UUID/retry identity, lifecycle/cycle request contract |
| NEW canonical_stewardship/request_fingerprint.py | Strict parser/serializer/schema, full byte vectors and DB-compatible digest |
| NEW canonical_stewardship/user_client.py | Injected authenticated RPC-only wrapper/protocol, no service-role configuration and no implicit write retry |

No modifications to data_fabric/adapters/supabase/client.py or config.py proposed; new wrapper avoids their required service secret. No human UI/API wiring is activated. Existing provisioning consumers of direct profile writes may become incompatible: identify them and either keep them disabled or accept an explicit additional migration to controlled administration before traffic. No production provisioning change is silently authorized by this inventory. The runtime administration/deprovisioning orchestrator, bootstrap tool and retention administration implementation paths remain missing decisions: retain this as a scope blocker, not a claim of complete implementation readiness.

| Exact proposed test/support path | Required future scope (NOT RUN) |
|---|---|
| tests/test_account_resolution.py | Exact raw aliases, override precedence, direct dispatch/commit and snapshot failure outcomes |
| tests/canonical_stewardship/test_stewardship.py | v2 adapter/read/receipt contract, role/domain/SoD and revocation cases |
| tests/security/test_production_tenant_provisioning.py | Updated status/FK/controlled profile static compatibility assertions; no mocked replacement for DB behavior |
| NEW tests/security/test_g08_identity_boundary.py | User client identity, deny-first and admin boundary scenarios |
| NEW tests/canonical_stewardship/test_request_fingerprint.py | Golden byte/digest vectors and malformed/default/limit cases |
| Successor-local tests/conftest.py; test_fg002.py; test_authority.py; test_replay.py; test_uid_retention.py; test_relationships.py; test_chain.py under tests/ | Actual isolated PG17.6 role/ACL/RLS/SoD/concurrency/FK/rollback and full 29-artifact replay, exact catalog/object preservation |
| Successor-local manifest.json; SHA256SUMS.json; README.md; validate_package.py; separate certification/evidence directory | Parent provenance, exact derivation/order, raw/application/harness hashes, frozen bytes and separate results |

Successor directory/CLOSE number is assigned only at separate Gate B authorization. Bootstrap/admin/retention schema annex and orchestration paths must be fixed before that instruction. Existing source/static tests referencing original SQL must not be misrepresented as behavior tests of derived successor bytes. Historic evidence remains untouched; new tests explicitly point to successor artifacts.

Migration quiescence remains mandatory: app/worker/managed jobs/direct RPC callers stopped and verified by accountable operator, no intermediate business access, traffic withheld through actual acceptance. Guard fixes do not make earlier email policies safe for traffic. Define controls/owner/window before execution; no proof of working quiescence exists in this source review. Preserve original transaction/STOP/unknown-commit ledger rules. SU-513239 remains unresolved in working context; no hosted fact was refreshed.

UNRESOLVED: exact DDL/trigger/helper signature annex; orchestration/bootstrap/retention paths; full vectors and any session-validation expansion; G08/G09/checkpoint reconciliation; scoped operator controls. Recommendation: accept inventory only after preceding decisions resolve, then issue separately bounded implementation authority. Reviewers: Database, Application, Independent Certification, PO; Identity/Retention/Stewardship for inherited blockers.

## Consolidated reviewer decision matrix — no selections

Each row: UNSELECTED: ACCEPT / REJECT / CONDITIONALLY ACCEPT. A recommendation is not an approval. Reviewer identity/date/evidence/rationale/conditions and condition owner/gate remain UNRECORDED.

| ID | Exact choices for reviewer | Recommendation | Required roles / blocking Gate A evidence |
|---|---|---|---|
| R01 | Bounded raw-role table vs explicit legacy alias expansion; merged item/typed mapping | Bounded table, item wins, all paths guarded | DB, Security, App, PO; role and field/type truth tables |
| R02 | A authenticated user vs redesigned capability; grants/SQL validation | A with DB validation and RPC-only user wrapper | DB, Security, App, PO; privilege/session/API and SERVICE-01 reconciliation |
| R03 | Typed admin/version model vs accepted equivalent; root/identity administration | Separate identity-admin, scoped root, immutable versions and controlled bootstrap | DB, Security, Stewardship, App; DDL/signatures, admin digest/storage and bootstrap/lock annex |
| R04 | Pairwise vs three humans; strict hold vs separate recovery policy | Pairwise Auth UUID checks, no authority resurrection or reopening | Domain, Security, DB, PO; evidence links and held-review consequences |
| R05 | Explicit P inheritance vs extra role assignments; replacement/retention rules | P inherits lower business edges, no SoD bypass; state-only canonical | Domain, Retention, DB, PO; full matrix, replacement and archive predicate |
| R06 | Exact v2 vs alternate input/serialization limits; legacy handling | Single evidence source, SHA-256 DB verification, strict v2 | DB, App, Security, Domain; complete mutation golden annex and compatibility decision |
| R07 | RESTRICT vs immediate/deferred NO ACTION; retain/delete/session/hold policy | RESTRICT, inactive deny-first, retained attribution | Retention, Identity, DB, App, PO; durations/holds/session assurance/partial failures |
| R08 | Six-artifact/29-step proposal vs further necessary expansion; final allowlist | Assess LAST after other contracts; freeze only explicit complete dependencies | DB, App, Certification, PO; DDL/object/file/orchestration and quiescence annex |
| R09 | Scoped reads replace this G09 dependency vs continued separate service consumer | Scoped summaries/receipts; G09 not silently executed/closed | DB, Security, App, Domain/G09; projection, receipt failure examples, consumer disposition |

## Gate A blockers, circulation and gate boundaries

Gate A acceptance blockers: actual reviewer choices absent; exact mapping/admin fields and signatures not fully frozen; root/bootstrap/succession and admin digest/receipt storage undecided; natural-person SoD and historical expiry/hold semantics undecided; retention hold/admin model, durations and session guarantee missing; full mutation golden vectors missing; user/admin/orchestration implementation inventory incomplete; profile-write consumer compatibility unresolved; changed SERVICE-01/UID-01/G09/acceptance dispositions not reconciled. Do not conditionally defer these implementation-determining choices to migration time.

Proposed circulation order: (1) Database + Identity/Security + Application jointly R01–R03; (2) Stewardship/Domain + Security + Data/Retention R04–R07, with R06 reviewed jointly by DB/App; (3) Application/G09 owner + DB/Security R09; (4) Database/Application/Independent Certification derive R08 last; (5) PO receives consolidated recommendations and actual unresolved exceptions. Real reviewer identities and appointments remain unassigned.

Gate A reviews this version/hash, source baseline and missing design annexes, not future candidate PASS. Gate B separately authorizes implementation only after resolved scope. Gate C freezes/hashes SQL, app and harness before separately authorized isolated certification; any changed executable bytes require applicable reruns. Gate D independent reviewers accept exact successor seal and evidence. Gate E separately resolves hosted readiness/G06/G09/G12, recovery/window/quiescence and staging authority; actual Auth/session/tenant acceptance precedes traffic. Production remains separately unauthorized.

## Document integrity and authorized-change statement

Line count and SHA-256 are reported in the accompanying Codex completion response after finalization. A document cannot embed its own final SHA-256 without changing that hash; the external digest binds this exact file. No placeholder is represented as a computed digest. The source v0.1 hash above is independently computable and unchanged.

Only this authorized Markdown document is created by this preparation. Existing CLOSE-014/015/016 file hashes are compared before/after and reported externally. No code/SQL/manifests/decision sheets/checkpoints are edited; no successor artifacts, Git operations, SQL execution, PostgreSQL/Supabase/hosted/credential operations, tests or approvals occur. In-memory reference-string hashing is documentation calculation, not certification or executed tests. This statement does not claim an unrelated concurrent workspace change was audited outside the compared package directories.

Gate A PENDING. Implementation UNAUTHORIZED. **STAGING EXECUTION NO-GO. PRODUCTION NO-GO.**
