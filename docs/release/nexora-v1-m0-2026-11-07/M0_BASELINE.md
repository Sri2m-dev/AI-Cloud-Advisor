# Nexora V1.0 - M0 release baseline

Date: 7 November 2026, Asia/Calcutta. Status: M0 PREPARATION COMPLETE; candidate certification and release NOT READY. This document records preparation, not a test result or technical acceptance.

## A. Authority and release snapshot

The Product Owner adopted the Final Product Release Plan and authorized M0 only. The 7 November G08 approval closes the PO design-decision phase for its accepted directions. Do not repeat those approvals. Database, Identity/Security and Application acceptance and mandatory Gate A/B2 criteria remain pending. This package starts no M1 work and authorizes no deployment.

Observed branch: `program/nexora-production-activation`.

Observed HEAD: `3b4a1100d86ef05dd915cf1734a2c4fa6581c299`.

Before these M0 documents: 55 modified tracked files; 276 visible untracked files; 2,082 tracked index entries. No staged changes were reported. Git could not enumerate the protected `.local/nxr-g06-pg17-disposable-01/` directory. It is excluded local runtime, not candidate content; no access escalation was attempted. Counts are therefore explicitly visible-worktree counts, not a claim to inventory inaccessible local files.

`nexora_release.py` currently says `1.1.0`; local tags already include `v1.0.0` and `v1.1.0`. "Nexora V1.0" is the delivery-program label in this package. No runtime version, existing tag, release history or commit was changed. A new non-colliding publication identifier must be selected before packaging/tagging; this does not block M1 safety work.

### Inventory files and inclusion rules

- `release_baseline_manifest.json`: branch/HEAD/tree, critical-source hashes, limits and authority.
- `candidate_inventory.csv`: every visible modified/untracked path at the pre-M0 snapshot, proposed disposition and raw SHA-256 where content inspection is permitted.
- `tracked_index_inventory.csv`: every tracked path and index blob/mode; historical baseline identity without reading all file contents.
- `route_catalogue.csv`: all 113 page files; existing navigation aliases; proposed release classification. It does not grant access or prove browser operation.
- `launch_blockers.csv`: single L01-L15 tracker with milestone, dependency, acceptance and role.
- `VERIFICATION.md`: existing commands, workflow behavior and future execution boundaries.
- `preservation_verification.json`: post-preparation hash/status checks.
- `SHA256SUMS.json`: integrity inventory of this documentation package, excluding itself.

Disposition totals: 52 required implementation paths; 9 engineering-document paths; 27 test-only paths; 3 governed SQL/fixture paths; 210 historical staging evidence paths requiring restricted review; 30 excluded metadata-only paths.

The 91 INCLUDE paths are the minimum changed-file reconciliation set, not an isolated application bundle. The release also needs unchanged dependencies from HEAD and all future M1-M5 fixes. No code change is accepted solely because it appears in this inventory.

Required integration groups:

| Group | Must travel together | Disposition |
|---|---|---|
| UI authentication and tenant identity | `utils/auth.py`, login/logout pages, authenticated/connector contexts, auth manager, associated tests | Include security fixes together; no legacy-session fallback |
| API identity/revocation | backend auth/security/token-store/middleware changes and untracked `backend/api_user_store.py`, tests and configuration documentation | Include together; API remains conditional/private until qualified |
| Canonical application, approval and risk reads | modified pages, repositories, services and canonical-read/SLA/tenant tests | Include coupled query and authority corrections |
| Financial ingestion/publication | modified ingestion/connector code; new financial repository, adapter, orchestrator, composition, verifier and component; regression tests | Include dependencies; live connector activation remains separate |
| Relationship integrity | modified Data Fabric adapters/contracts, EMRP and relationship repository/tests | Include together; preserve confirmed-write controls |
| Provisioning and bootstrap | modified provisioning/audit scripts/services/tests, inventories and Auth UID migration | Include reviewed artifacts; migration inventory is not execution authority |
| SQL and replay fixtures | three non-staging SQL/fixture additions and replay harness/tests | Governed migration/test content only; never app-startup replay |
| CLOSE evidence | staging packages/reports/design inputs | Preserve immutable originals; restricted engineering evidence, not runtime image/public attachments |
| Local/restoration material | metadata-only exclusions in CSV | Preserve in place; never read/hash/package as M0 candidate content |

Future candidate inclusion must not use `git add .`, include local secret files or promote historical staging SQL merely because it is untracked. No staging or commit occurred during M0.

## B. Supported feature and route catalogue

Scope: authenticated single-node evidence-led product; controlled organization onboarding; governed evidence import; supported analysis/Ask; human approval/decision and evidence trace; durable encrypted resume and authorized exports. No new framework is needed.

| Feature | Candidate page files under `pages/` | Acceptance boundary |
|---|---|---|
| Authentication | `login.py`, `logout.py` | Actual production Auth, tenant binding, logout and invalidation |
| Home/persona | `welcome.py`, `executive_command_center.py`, `ceo_workspace.py`, `cio_workspace.py`, `cfo_workspace.py`, `finops_workspace.py`, `operations_command_center.py` | Existing role guards remain authoritative; absent authority is UNKNOWN |
| Evidence journey | `analyze_environment.py` | Admit, confirm/reject, execute supported measures, resume exact encrypted analysis |
| Enterprise context | `enterprise_registry.py`, `relationship_explorer.py`, `dependency_analysis.py`, `technology_digital_twin.py`, `application_inventory.py` | Governed sources only; no fabricated graph when prospect inputs lack it |
| Financial views | `enterprise_spend.py`, `cost_intelligence.py` | Currency/scope/period/lineage preserved; missing measures fail closed |
| Ask | `enterprise_ai_copilot.py` | Existing universal Ask blocker resolved against accepted supported-capability contract; no canned-answer substitute |
| Decisions/approvals | `decision_intelligence.py`, `approval_center.py` | Accepted G08 controls, separation and immutable history enforced |
| Operations/customer controls | `audit_timeline.py`, `organization_administration.py`, `reports.py` | Scoped audit, controlled team administration, authorized export |

23 page files are SUPPORTED_CANDIDATE, 8 CONTROLLED_SUPPORTING, and 82 DEFERRED_NOT_PUBLIC_V1. Exact file-level catalogue is in CSV. Controlled support includes prospect intake, data quality, cloud cost imports/account resolution/registry and Data Fabric/entity/business-service evidence surfaces. It does not enable live cloud access.

Current navigation is broader than this release catalogue. M4 must enforce the supported surface, including direct page access, without granting new roles or merely hiding sidebar links. Streamlit page filenames are implementation routes; M4 must capture the actual deployed browser URLs and aliases. No URL/HTTP-200 claim is made in M0.

Backend API is internal/conditional; do not advertise a public developer API until L14 is closed. Health is operational liveness, metrics are restricted operational data. Live connectors, autonomous execution, self-service billing, broad forecast/scenario surfaces, multi-node scaling and sales/demo-only routes are deferred or separately controlled. No dormant route is technically accepted by exclusion.

## C. One actionable launch tracker and milestone dependencies

`launch_blockers.csv` is the single actionable L01-L15 tracker. Every row is OPEN or CONDITIONAL_OPEN, with a responsible role but no invented individual assignment. M0 creates neither a PASS nor an exception.

| Milestone | Dependencies | Exit evidence |
|---|---|---|
| M0 baseline | This instruction | Complete visible inventory/catalogue/tracker; limitations and staffing recorded; existing work preserved |
| M1 security/packaging | M0; safety-work owners | L01/L06/L13 corrected; CI/CD promotion/exposure safeguards prepared; exact changed-file tests and artifact review |
| M2 G08 implementation | M0; Database/Security/Application owners | Implement approved directions; negative/concurrency/effective-privilege tests; actual technical acceptance and mandatory gate criteria |
| M3 operational target | M0/M1; funded target/DNS/secrets operator | TLS, persistent DB/files/keys, backup/restore, alerts, target identity and operating limits |
| M4 product closure | M2/M3; inference/access configuration | Supported onboarding-to-analysis/Ask/decision/export/resume journey; scope restrictions; browser/accessibility acceptance |
| M5 certification | M1-M4 | Exact-candidate fresh build/regression/target tests, classified skips, independent reviews; zero scope P0/P1 |
| M6 public release/handover | M5 and required release controls | Authorized rollout, public smoke, incident ownership, observation evidence and operations handover |

Finite backlog: 15 blocker records plus version/route-baseline reconciliation. Any new task must close one of these criteria or be placed on the post-launch backlog. No new open-ended design program or recurring G08 PO review is created.

## D. Minimum safe M1 change sequence (PROPOSED ONLY)

1. Assign Application/Release and Security operators. Confirm preservation snapshot and create an explicitly selected candidate branch later if needed; no bulk staging or worktree reset.
2. L01: authorized credential custodian rotates/revokes the identified historical credential and reused values, reviews access logs and returns sanitized evidence. Do not infer closure from the later reported successful password reset alone.
3. L06: narrow container context/exclusions for keys, `.local`, evidence/logs/customer artifacts; prefer clean candidate input. Add bounded artifact-hygiene checks; inspect built image contents later under build authority. No image publication.
4. L13: replace static readiness approval/percentages with evidence-backed or unavailable/UNKNOWN results. Review all consumers; do not build a new readiness framework. Add a focused regression and use existing release tests.
5. L09: make image promotion/webhooks depend on exact-candidate passing checks and applicable protected release approval. Review multi-service coherence; do not trigger workflows, publish images or deploy during preparation.
6. L14/L15: prepare the existing ingress/telemetry configuration so unqualified API/metrics/admin surfaces are not public. If API is required by frontend flows, retain necessary internal reachability and test that integration. Do not deploy default telemetry credentials. Credential hashing/rate controls are required before any public API exposure.
7. Record evidence and modified-file hashes; run only separately permitted local verification. M1 completion does not close M2-M6 or advance gates.

M1 proposed edits: `.dockerignore`/container packaging tests; `services/release_readiness_service.py` and necessary callers; `.github/workflows/cd.yml` and CI handoff; scoped ingress/telemetry settings if needed. Do not modify sealed CLOSE packages, G08 approval direction or unrelated features.

## E. Verification

See `VERIFICATION.md`. Commands are identified, not executed. Full pytest is not SQL-free: local fixtures can create SQLite/disposable PostgreSQL state; opt-in integration modes may use external systems. M0 ran no tests, imports, builds, containers, SQL or workflow dispatches.

## F. Missing owners, access and genuine execution dependencies

| Dependency | Current state | Blocks |
|---|---|---|
| Release/Application lead | Individual UNASSIGNED | Accountable M1 edits and candidate freeze |
| Security/credential custodian | Individual UNASSIGNED | L01 external closure and security acceptance |
| Database engineer + independent reviewer | Individuals UNASSIGNED | M2 implementation/technical acceptance |
| Identity/Security and Application reviewers | Individuals UNASSIGNED | Relevant technical acceptance; not a repeat PO design approval |
| Operations/DNS/hosting operator | Individual UNASSIGNED; target/budget/access unverified | M3/public endpoint/recovery/monitoring |
| QA/product acceptance owner | Individual UNASSIGNED | M4/M5 evidence |
| Legal/privacy/support owner | Individual UNASSIGNED | L12 and operational handover |
| GitHub maintainer/environment rights | Not verified | Protected CI/CD changes and eventual promotion; never current dispatch authority |
| Credential provider/project access | Not supplied/verified here | Rotation/log review and later target checks; no secrets requested in chat |
| Production platform, region, DNS/domain and budget | Not selected/verified in M0 | M3; does not block local M1 packaging/readiness corrections |
| Provider configuration and permitted evidence processing | Not verified | Ask live qualification in M4; not all M1 work |
| Workload, latency, upload limits, availability, RPO/RTO | No accepted numeric release targets captured | M3/M5 capacity/recovery acceptance |
| Public artifact version | `V1.0` program vs `1.1.0` source and existing tags | Final metadata/tag/package identity; not M1 safety work |

PO decisions still needed are operating/commercial parameters: funding/hosting constraints, public artifact naming where needed, service capacity/recovery objectives, terms/privacy/support and accountable appointments. No explicitly accepted G08 direction is reopened. A technical ambiguity is routed to the responsible technical reviewer, with PO escalation only for a concrete policy change or safety conflict.

## G. Recommendation and stop

M0 preparation: GO / COMPLETE WITH DECLARED LIMITATIONS. M0 does not produce a frozen executable release candidate. M1 start: staffing/access conditions above remain; work is not started by this document. Public release: NO-GO until mandatory blocker/gate evidence is complete.

No existing application, workflow, SQL, guard, tag, index or commit was changed. Only this new M0 documentation directory was created. Pre-existing readable candidate bytes, critical sources and tracked index identities are checked in `preservation_verification.json`. Metadata-only restricted paths are not claimed content-verified.

Stop after M0. G08 PO decision phase CLOSED BY APPROVAL; DBR-01/DBR-02 technical acceptance pending; Gate A/Gate B2 pending mandatory criteria; staging/production remain subject to existing readiness/release controls and are not authorized by this package.
