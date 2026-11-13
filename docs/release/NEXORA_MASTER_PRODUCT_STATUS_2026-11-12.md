# NEXORA Master Product and Evidence Reconciliation

Review date: 2026-11-12
Repository: `Sri2m-dev/AI-Cloud-Advisor`
Branch: `program/nexora-production-activation`
Review type: repository and supplied-evidence reconciliation; no cloud API, project, database, or protected-resource access.

## Executive summary

**Current recommendation: NO-GO for production activation and a general commercial launch.** NEXORA has substantial reusable local product and PostgreSQL qualification evidence. It does not yet have a single frozen, current candidate whose migrations, authentication, customer workflow, Ask, recovery, cost, and operational controls have all been accepted together.

### Final dependency-closure addendum — 2026-11-13

The final reachable-dependency pass classified all six SC-001-required
application/spend objects without adding SQL: three are superseded for V1
customer reads by canonical Data Fabric/P1 services, and three are excluded
through enforced route scope. Cost Intelligence, Dependency Analysis, and
Technology Digital Twin are denied by the server-side page policy; `/api/v1/cost`
is unmounted and returns 404. The canonical Application Portfolio continues to
report application spend as `UNKNOWN`.

The complete V1 database contract remains **NO-GO**: 20 M0 candidate pages
remain role-eligible and are not all database-contract qualified. The M0
catalogue still says proposed / `NOT_CURRENTLY_CERTIFIED`. The new
[dependency reconciliation](./nexora-v1-final-dependency-closure-2026-11-13/DEPENDENCY_RECONCILIATION.md),
[route matrix](./nexora-v1-final-dependency-closure-2026-11-13/UPDATED_ROUTE_MATRIX.md),
[regression results](./nexora-v1-final-dependency-closure-2026-11-13/REGRESSION_RESULTS.md),
and [blocker list](./nexora-v1-final-dependency-closure-2026-11-13/REMAINING_BLOCKERS.md)
record the evidence and limitations. The existing browser target was
unresponsive, so no authenticated browser journey was claimed. Production
readiness remains **NO-GO**.

The Enterprise Registry V1 composition now uses only the canonical Data Fabric
source, and six focused service tests pass, including denial of legacy-only
rows. This does not qualify its production page: operations Compose gives the
frontend an anon key and mounts the service-role secret only in the API
container. A safe authenticated backend reader or route exclusion is still
required; the service-role secret must not be exposed to the browser.

1. **What is actually complete?** The immutable local-first v1.1 release has a historical local certification. A synthetic, PostgreSQL-backed customer workflow and complete encrypted local backup/restore were separately qualified. Isolated CFO and database-authorization mechanics also have successful test evidence. These are bounded qualifications, not proof of a deployed commercial service.
2. **What remains incomplete?** The current modified worktree is not a frozen release; 29 database API object names still lack creation definitions and live Supabase schema/RLS state is unverified. The legacy approval table callers have been removed from the reachable customer journey in favor of the existing event workflow. The three unknown Cost Intelligence dependencies are now route-excluded, and the six SC-001 objects have been superseded or excluded for the core customer workflow; neither action creates those legacy contracts. Twenty other M0 candidates remain role-eligible and are not all database-contract qualified. The r5 authenticated application and CFO page do not yet form one accepted browser journey; universal Ask acceptance needs source/version reconciliation; off-host recovery and measured/approved RPO/RTO are absent; G08 application operations remain fail-closed; customer pilot, support, terms, and actual operating costs are not evidenced.
3. **What can be reused?** The PostgreSQL customer-workflow repository and recovery package, synthetic A/B tenant tests, restore verification/runbook, local financial publication candidate and tests, M1 packaging controls, and isolated M4 CFO/SQ-DB evidence. Reuse does not make their separate scopes a single deployment.
4. **What is currently costing money?** Unknown. The owner supplied that the Supabase organization is Pro and three projects are active/healthy. No current invoice, billing export, or per-project usage was inspected. The only numeric cloud-cost artifact found is an archived **$10.18/month estimate** for additional compute and disk on a historical restore configuration; it is not actual spend or a current quote.
5. **Top five actions toward sellability:** (1) designate and freeze an exact release candidate; (2) reconcile and replay the complete canonical migration/bootstrap chain in a new disposable target, then compare to authorized read-only service exports; (3) qualify one integrated authenticated A/B browser journey against its actual financial/evidence dependencies; (4) close the customer-facing Ask/pilot acceptance and commercial/support obligations; (5) establish independently tested recovery, ownership, and an evidence-backed cost envelope.
6. **Single next executable task:** close the canonical Data Fabric reader boundary safely (authenticated backend reader or route exclusion), then inventory and qualify the database dependencies of the 20 remaining role-eligible M0 candidates. Verify authoritative contracts on a fresh isolated database or exclude each route through server-side policy, then perform one authenticated browser acceptance against a frozen candidate. Do not infer schemas from SELECT callers, expose a service-role secret to the frontend, or modify protected Supabase projects.

### Verdict snapshot

| Area | Current conclusion |
|---|---|
| Local synthetic product functionality | **GO within the individual recorded qualification scopes** |
| PostgreSQL tenant authorization | **GO within the tested isolated scopes; not production-certified** |
| Six SC-001 object paths in the approved customer workflow | **GO within the current route profile: 3 superseded, 3 excluded, no speculative DDL** |
| Complete local encrypted PostgreSQL backup integrity | **GO for the tested fresh PostgreSQL 18 restore** |
| Existing Supabase schema/RLS/migration state | **NOT VERIFIED** |
| Canonical full production bootstrap | **NO-GO / PARTIAL LOCAL QUALIFICATION** — the 43-file chain and bounded workflow have test-only replay evidence; zero of the 29 object definitions were added, legacy approval and excluded Cost/graph/technology routes were removed from the core path, 20 candidate routes remain unqualified, and hosted runtime remains unresolved |
| Independent/off-host recovery | **NO-GO** |
| RPO/RTO | **NO-GO; targets proposed only, actual values not measured** |
| G08 application operation | **NO-GO; remains fail-closed** |
| Production activation / overall sellability | **NO-GO** |

This report does not change any product, recovery, or release gate. The supplied Supabase projects remain protected and unchanged.

## Evidence scope and limits

### Repository and worktree snapshot

The observed `HEAD` is `3b4a1100d86ef05dd915cf1734a2c4fa6581c299` (`3b4a1100`, 2026-10-09), and the branch is 12 commits ahead of its recorded upstream and 0 behind. At review start, the worktree had **96 modified tracked files** (5,789 insertions / 2,767 deletions by `git diff --stat`) and **636 untracked paths**. These pre-existing changes include product code, tests, SQL, deployment templates, reports, and evidence; they were preserved. This qualification adds scoped source, test, and report changes without staging or cleaning unrelated work. A frozen-release certification must identify and review an exact resulting artifact; the old `v1.1.0` release commit is not the current worktree.

Local inventory found **19** files under `supabase/migrations/` and **28** SQL files under `database/contracts/`. These are repository files, not proof that any matching service schema was installed. For this qualification, `deploy/production/bootstrap-manifest.json` was corrected to list all 19 dated public migrations, including the two October Auth/profile migrations, and remains `BLOCKED` / non-executable. Its PostgreSQL replay field records only the network-disabled test replay. The P6 report now records all 43 PostgreSQL inputs completing in the disposable test harness; the earlier 0020 compilation failure and 0021–0023 stop are historical and superseded. The complete application schema and hosted Supabase behavior remain unverified, with 29 distinct API object names still lacking creation definitions. The focused run and precise limitations are documented in the [canonical bootstrap qualification package](./nexora-v1-canonical-bootstrap-2026-11-12/IMPLEMENTATION_REPORT.md). NXR-DASH-10 is a standalone candidate outside the blocked migration manifest, not an installed replacement.

The report uses each test result only for the scope stated in its evidence file. Counts below are independent recorded runs and **must not be added into one aggregate regression total**.

### Supabase evidence boundary

The following status was **supplied by the user as independently verified on 2026-11-12**. Organization `qqxmsutyttqicslgypah` is reported as Pro. The projects were not independently queried during this review:

| Project | User-supplied service observation | Review limitation |
|---|---|---|
| `nexora-p3-validation` (`ageubmyosicypqqkdvox`) | `ACTIVE_HEALTHY`, PostgreSQL 17.6, `ap-southeast-2` | Schema, RLS, migration ledger, roles, backup settings, endpoint, networking, billing not queried. |
| `nexora-p3-validation-restoration` (`uuqprdnqhbsmwubeqouw`) | `ACTIVE_HEALTHY`, PostgreSQL 17.11, `ap-southeast-2` | Same as above; no restore or compatibility test performed. |
| `AI-Cloud-Advisor-Dev` (`iafrrtmvvqmuksvprrsj`) | `ACTIVE_HEALTHY`, PostgreSQL 17.6, `eu-west-1` | Same as above; specifically treated as protected and not a recovery target. |

All three projects are in the reported Pro organization. No Supabase inspection tool was available in the connected-tool inventory, and no cloud API or project connection was attempted. Historical repository evidence is older and must not be presented as a fresh query. No customer rows, credentials, or service secrets were read.

### Codex/session evidence boundary

The session inventory exposed six relevant sessions in this workspace:

| Session metadata | History available to this review |
|---|---|
| `NEXORA V1 backup and recovery qualification` (2026-11-12) | Current conversation and three checkpoints were available: `001-building-complete-postgresql-r.md`, `002-completing-postgresql-recovery.md`, and `003-reconciling-nexora-product-evi.md`. |
| `Nexora M4 financial integration steps` (2026-11-11 to 2026-11-12) | Session metadata available; transcript lookup returned an empty transcript. |
| `Nexora application activation and testing` (2026-11-10 to 2026-11-11) | Metadata available; transcript lookup empty. |
| `Nexora API authentication remediation` (2026-10-11 to 2026-10-13) | Metadata available; transcript lookup empty. |
| `NXR-DASH-09 Security Contract Closure and Non-Executable PostgreSQL Migration Draft` (2026-10-14 to 2026-10-15) | Metadata available; transcript lookup empty. |
| `Supabase Auth migration correction plan` (2026-10-09) | Metadata available; transcript lookup empty. |

The local session database returned only the current recovery/reconciliation session. Thus the five older session transcripts, their execution logs, and any unretained Codex task records could not be reviewed. Their decisions are reconstructed only from retained repository reports, commits, and evidence; this is not a claim that the full Codex history was available.

## 1. NEXORA Master Product Status

| Capability | Classification | Evidence-backed state and boundary |
|---|---|---|
| Frozen local-first release | **Verified complete — historical baseline only** | [Local product certification](../production/NEXORA_FINAL_LOCAL_PRODUCT_CERTIFICATION.md) records v1.1.0 and local-first evidence/Ask/Decision Intelligence certification. [Final release record](./NEXORA_V1_FINAL_RELEASE.md) records a frozen release and external Supabase/AWS/Azure certification deferred. Neither certifies the current dirty worktree. |
| M0–M3 release preparation | **Implemented, local checks passed; release acceptance open** | M0 says preparation complete but no frozen candidate. M1 reports 131 passed and external/runtime-image actions open. M2A/M2B/M2C report 28/98/326 offline tests respectively; those reports explicitly did not prove PostgreSQL behavior. M3 reports 385 offline tests and Compose schema validation, but no containers, PostgreSQL, real identity, live alerts, or staging runtime were executed. See the [M0](./nexora-v1-m0-2026-11-07/M0_BASELINE.md), [M1](./nexora-v1-m1-2026-11-07/M1_EXECUTION_REPORT.md), [M2A](./nexora-v1-m2a-2026-11-07/M2A_IMPLEMENTATION_REPORT.md), [M2B](./nexora-v1-m2b-2026-11-07/M2B_IMPLEMENTATION_REPORT.md), [M2C](./nexora-v1-m2c-2026-11-08/M2C_IMPLEMENTATION_REPORT.md), and [M3](./nexora-v1-m3-2026-11-10/M3_IMPLEMENTATION_REPORT.md) records. |
| Authenticated customer workflow | **Verified complete — isolated synthetic scope** | The [V1 journey report](./nexora-v1-customer-journey-2026-11-12/qualification.md) records authenticated A/B workflow, workspace, evidence, Ask/decision, Finance/CIO/executive approvals, and evidence-linked export checks against PostgreSQL. The complete local recovery test repeated service-level validation on a fresh PostgreSQL 18 cluster. A browser session against the recovered DB was not run. |
| JWT/session and tenant authorization | **Verified in isolated scopes; not accepted as production posture** | The [SQ-APP report](./nexora-sqapp-auth-activation-2026-11-11/REPORT.md) records actual GoTrue/FastAPI authentication and A/B tenant denials for synthetic accounts, but its r5 browser login was not executed and the CFO page failed on a missing `tenant_cloud_financial_posture` RPC. The separate [M4 CFO integration](./nexora-m4-cfo-integration-2026-11-11/REPORT.md) did execute Chrome login/workspace selection/render/logout/reauthentication for synthetic A/B against a separate isolated financial project. Do not combine these into one deployment claim. |
| Evidence, approvals, decisions, export durability | **Verified complete — synthetic recovery checks** | Recovered service checks verified Customer A evidence decryption/hash, Ask, decision, three approval roles, and evidence-linked export; Customer B access was denied. This was not a recovered-database browser session or customer-data acceptance. |
| Ask Nexora | **Partially implemented; acceptance basis needs reconciliation** | Governed planning/execution code and a historical local certification exist. The specific [universal Ask blocker](./UNIVERSAL_GOVERNED_ASK_BLOCKER.md) records an unsuccessful live planner request (HTTP 401) and says universal-query/browser acceptance remains blocked; another local certification claims a prior controlled live Ask pass. The current candidate/provider/configuration and approved Ask contract are not mapped to one exact accepted build. Bounded synthetic Ask is not evidence of universal query acceptance. |
| CFO/financial evidence publication | **Implemented but not accepted for hosted use** | [NXR-DASH-10](../cmp/NXR-DASH-10-implementation-results.md) and [RC-02](../cmp/NXR-DASH-RC-02-local-acceptance.md) tested the local PostgreSQL candidate, dashboard composition, A/B isolation, and fail-closed defaults (RC-02: 14 PostgreSQL tests and 194 focused tests). M4 CFO integration separately passed its isolated financial scope. D1–D8, source attestation authority, migration, hosted Auth/RLS, and live AWS evidence remain pending. |
| AWS/Azure live connectors | **Partially implemented / externally blocked** | Git history includes AWS runtime identity/External-ID work and Azure canonical ingestion/onboarding. No current customer AWS/Azure connection or live discovery was demonstrated. Azure Start Discovery remains explicitly blocked in RC-01 and NXR-DASH records. AWS financial publication defaults to NOT_READY without approved authority and source evidence. |
| PostgreSQL customer workflow backup | **Verified complete — local backup integrity only** | The 2026-11-12 closeout reports a complete encrypted package and fresh-cluster restore, including globals/ownership/ACL/RLS/functions/extensions/migrations/workflow/evidence checks. It reports 51 + 1 + 66 + 37 passes across separate test slices; do not treat that as a unified total. No off-host restore or production schedule was tested. |
| Canonical application bootstrap/migrations | **Partial local execution; full bootstrap NO-GO** | The updated [P6 report](../cmp/CMP-P6-DEF-001/REPORT.md) records a fresh, test-only replay of all 43 PostgreSQL inputs, catalog and public tenant assertions, and the customer-workflow service journey on the newly bootstrapped database. The former 0020 syntax failure is superseded; 0021–0023 executed. The production manifest now includes all 19 dated public migrations and is explicitly blocked/non-executable. The current inventory still has 29 unresolved database API object names and no hosted Supabase/runtime or full browser certification. The focused PostgreSQL/bootstrap/auth/workflow/finance/recovery regression run passed 172 tests; scope and limits are in the [canonical bootstrap qualification package](./nexora-v1-canonical-bootstrap-2026-11-12/IMPLEMENTATION_REPORT.md). |
| G08 privileged owner operations | **Blocked; correctly fail-closed** | The [trusted-execution report](./nexora-m4-g08-trusted-execution-2026-11-11/qualification.md) records partial isolated PostgreSQL mechanics, including concurrency and lost-ack reconciliation. The [M4 application reconciliation report](./nexora-m4-g08-application-reconciliation-2026-11-11/REPORT.md) is NO-GO: no production operator/policy/evidence/fencing providers or application integration; authenticated route intentionally returns HTTP 503. Do not activate G08. |
| Production operations and recovery | **Partially implemented; production not ready** | Local packaging, verification, retention, recovery runbook, measurement, and monitoring logic exist. The daily timer is not installed/enabled, alerts were not delivered, key escrow/rotation and named ownership are absent, and no independent host/target was used. Proposed RPO ≤24h and RTO ≤4h remain owner-acceptance proposals; measured values are unavailable. |
| Customer pilot / commercial acceptance | **Blocked / missing evidence** | The pilot checklist is unfilled; no accepted external customer journey, customer outcome, signed service/support commitment, or production hosting proof is in the reviewed evidence. Pricing in `docs/ga/COMMERCIAL_READINESS.md` is expressly a hypothesis. |

## 2. Codex Historical Decision Register

### Milestones and decisions that can be reused

| Milestone / decision | Historical outcome | Current applicability |
|---|---|---|
| M0 release baseline | Preparation complete; 15 launch blockers remained open/conditional; no release candidate or release authorization. | Reuse the blocker and route inventories, but reconcile them with current source and newer evidence. |
| M1 release safety | Local controls implemented and 131 scoped tests passed; credential custodian actions and runnable image/target qualification remained open. | Reuse deny-by-default Docker context and CI safeguards; do not treat exported scratch-image inspection as a production image build. |
| M2A/M2B/M2C G08 foundations | Offline structural/coordinator suites passed (28, 98, 326); success authority and real DB behavior remained blocked at the time. | Later SQ-DB runs qualify some synthetic DB mechanics only. They do not authorize actual G08. |
| SQ-DB PostgreSQL qualification | Later real isolated PostgreSQL 17.11 driver run reported SQL-core and commit-uncertainty acceptance, with 98 regressions and 8 isolation tests. | Reuse for the bounded synthetic DB transaction boundary, not application/browser G08, production identity, or a full bootstrap. |
| M3 operations | 385 offline tests and static Compose validation passed; no actual containers, PostgreSQL, live alert delivery, or staging were run. | Reuse the operational artifacts and readiness semantics; install/activation is still unproven. |
| M4 CFO / financial path | Isolated CFO browser and tenant-security tests passed for a separate synthetic project. | Reuse the test and adapter design; it does not supply the missing RPC in the distinct r5 Auth target or accept D1–D8. |
| NXR-DASH-10 / RC-02 | Synthetic local PostgreSQL publication and active-route composition passed; hosted activation and migration chain stayed blocked. | Reuse as local mechanics; preserve unconditional default denial and keep the SQL candidate outside migration automation until separately approved. |
| V1 backup closeout | Earlier “backup completeness NO-GO” was superseded by the later complete-package fresh local restore. | Local integrity is now GO only for the verified synthetic PostgreSQL 18 package. Off-host recovery, RPO/RTO, and production remain NO-GO. |
| Project and authority safety | Prior records repeatedly prohibit changes to retained Supabase projects and require G08 fail-closed behavior. | Still applicable. This review changed no project and did not activate G08. |
| Cloud architecture/cost | Historical archive identifies a Supabase restore project; ECS/Fargate/ALB/Redis/worker/telemetry stack is largely templates/proposal. | Do not infer deployments or charges from templates. Reuse the minimal one-app/one-DB pilot proposal only after price and operations owners accept it. |

### Recent committed history

The observed 12-commit branch delta contains these prior decisions (short hashes shown from the local log):

| Commit | Recorded change | Relevance |
|---|---|---|
| `3b4a1100` | Retire legacy Supabase Auth user trigger | Auth lifecycle hardening; does not certify current hosted schema. |
| `fceadad5` | Activate governed Azure canonical data path | Implementation milestone; Azure discovery remains externally blocked. |
| `e2383eb5` | Harden Azure customer onboarding | Reusable onboarding boundary. |
| `f9c88589` | Unify synthetic demo tenant identity | Reusable test/demo scope consistency. |
| `0b6c15c7` | Resolve production organization before executive navigation | Reusable tenant routing safeguard. |
| `6703891b` | Add controlled production tenant provisioning | Source implementation, not live provisioning proof. |
| `c77cf897` | Harden production persistence boundaries | Reusable persistence protections. |
| `f3e81d0c` | Separate Supabase runtime and privileged credentials | Relevant to the task-template secret review above. |
| `b873b000` | Define AWS runtime identity deployment contract | Deployment design only. |
| `a808fd70` | Wire AWS runtime identity deployment configuration | Source/configuration, not deployed AWS identity. |
| `c5127e7e` | Add portable AWS runtime identity | Reusable connector implementation. |
| `3c9a1f6d` | Generate and govern AWS connector External ID | Reusable onboarding/security contract; no customer role assumption is evidenced here. |

### Repeated investigations and superseded blockers

- The “local Docker is not off-host” and “no destination selected” finding recurs in the recovery, Gate 1, and cost-review work. The user’s new project observations identify three active projects but do not designate any as an authorized writable recovery target; Gate 1 remains blocked.
- The historical `$10.18/month` restore estimate is repeated in recovery and cost records. It remains an estimate, not actual spend or an INR 1,000 cost cap.
- The earlier local backup-integrity NO-GO was specifically superseded by the later complete-package local restore. It does **not** supersede off-host, timed-recovery, or production NO-GO.
- Offline-only M2 reports were followed by real isolated SQ-DB tests. This closes only the reported technical SQL/driver scope, not G08 route integration, hosted policy, or canonical full-chain migration.
- Auth, CFO, and customer workflow successes came from different targets and acceptance runs. Their results cannot be combined into an end-to-end hosted app pass.
- The active worktree and migration set have progressed beyond the older frozen release documentation. Re-certification must be performed on the exact candidate, rather than inheriting old “complete/frozen” labels.

### Prior approaches accepted or rejected

- **Accepted for bounded qualification:** synthetic A/B tenants; local fresh PostgreSQL clusters; fail-closed authorization; no public PostgreSQL; explicit migration/recovery packages; local-first product scope.
- **Rejected or not authorized:** using a second local volume as off-host recovery; assuming a Supabase `postgres` role supports global role restoration; applying NXR-DASH standalone SQL as a substitute for the canonical chain; treating a database-only restore as full service recovery; inferring cloud deployment/cost from ECS templates; using email, caller-supplied tenant hints, or synthetic G08 identities as production authority.
- **Still required:** independent operator/policy/evidence/fencing contracts for G08; signed D1–D8 decisions for hosted financial publication; a named and authorized target; external cost evidence; exact candidate acceptance.

## 3. Infrastructure and Cost Register

### Actual or user-reported infrastructure versus proposals

| Resource / architecture | Evidence class | Status, purpose, and cost relevance |
|---|---|---|
| Three Supabase projects listed above | User-supplied service observation (2026-11-12) | Reported active/healthy under a Pro organization. No billing allocation, schema/RLS, networking, backup, or current resource-level charges were inspected. Do not change any project. |
| Historical source and restore Supabase projects | Archived provider screenshots and local records in `deploy/staging/NXR-CLOSE-016/evidence/G07/` | Historical database-only restore from PG 17.6 to 17.11 in the same `ap-southeast-2` region. A closeout says retain the recovery project; deletion was not authorized. The newer user-supplied observation reports both active. This does not prove a separate provider/region failure domain or compatibility with current global-role package restore. |
| Prior cloud environment | Owner report, echoed in the cost review | Owner says a cloud environment was tested and shut down due to cost. No complete deployed-resource inventory, shutdown evidence for every resource, invoice, or historical total was found. |
| AWS ECS/Fargate, ALB, Redis/ElastiCache, Celery, NGINX, telemetry | Proposed architecture and placeholder task templates | Not proof of deployed resources. Five ECS task templates use placeholders; one each of the listed task families would total 2 vCPU/4 GiB by template sizing only, not a price or deployed count. No Terraform/CloudFormation stack or provider deployment output was found. |
| Local Compose / Docker Desktop | Repository deployment recipe and local qualification environment | Local configuration/execution only. Same workstation is not an independent recovery domain. |
| NXR-DASH-10 SQL and RPCs | Standalone local qualification candidate | Outside the blocked manifest and guarded default-deny. Not evidence of production schema or AWS billing activation. |

**Template security review item:** the ECS task templates include a `SUPABASE_SERVICE_KEY` secret reference in frontend, API, worker, and beat definitions (`deploy/ecs/task-frontend.json`, `task-api.json`, `task-worker.json`, `task-beat.json`). These are placeholders, not evidence that a key was deployed. Before any use, reconcile the frontend assignment with the M1 boundary that privileged credentials must not reach the frontend and with the runtime/privileged credential separation commit. Restrict elevated credentials to the minimum server-side workload that requires them; do not expose them to browser code.

### Historical, current, and estimated costs

| Cost evidence | Amount | Classification |
|---|---:|---|
| Archived 2026-10-18 restore confirmation | USD 9.68/month compute + USD 0.50/month disk = **USD 10.18/month additional** | Historical provider UI estimate for that restore configuration. Not an invoice, current quote, all-in cost, tax-inclusive amount, or INR budget proof. |
| Former cloud environment shutdown | Amount not provided | Owner-reported reason; repository has no invoice/billing export establishing the previous spend. |
| Current Pro organization and three active projects | **Unknown** | Could incur subscription, compute, disk, backup, network, or usage charges. No current billing statement, invoice, credits, or cost allocation was inspected. |
| AWS/Azure/GCP hosting and telemetry | **Unknown / not evidenced as deployed** | Templates do not establish active resources or current charges. |
| Commercial pricing hypotheses | $75k–$150k pilot; $250k–$750k/year; $100k–$300k deployment | Hypotheses in commercial-readiness material; not approved or contractual pricing. |

### Explicit parametric monthly model

No supported numeric monthly total is available. For a selected region, plan, measured workload, and accepted run window, calculate:

```text
monthly total =
  app compute (730 h × selected app rate)
  + managed PostgreSQL/Auth plan or instance (730 h × selected DB rate)
  + database disk + backup/PITR retention + I/O
  + encrypted evidence storage and requests
  + TLS ingress/private connectivity/NAT/transfer/egress
  + logs/metrics/alerts and retention
  + email/domain/secrets
  + applicable tax and minimum commitments
```

Planning assumptions for a **proposed** minimal pilot: one region, one bounded tenant, one small stateless app service, one managed Auth/PostgreSQL project, no replica, no continuously running worker/beat/Redis, no LLM/connector calls by default, bounded evidence, provider-native bounded logs/alerts. Every price input is currently unknown; the total is **TBD**, not zero. A one-time recovery quote must include compute duration, disk, backup storage, transfer/egress, private network, logs, taxes, and billing minimums and demonstrate a hard operational run limit under INR 1,000. Budget alerts alone are not a hard cap.

### Gate 1 and recovery suitability

**Gate 1 remains BLOCKED.** The source and historical restoration projects are in the same organization and region; their current observed status is supplied, but private paths, host/control-plane separation, global role/superuser privileges, current cost, and package compatibility have not been independently checked. The Dev project is in another region but is protected and cannot be treated as a recovery target. No target may be modified under this review. A future off-host drill requires a separately approved disposable destination/failure domain, scoped transfer and restore privileges, private connectivity, independent key custody, bounded price, and explicit write/provisioning authorization.

## 4. V1 Market Readiness Gap Register

Severity is relative to making a safe, supportable first paid pilot; owner names are not invented.

| ID / severity | Gap and current evidence | Accountable role | Closure criteria / evidence |
|---|---|---|---|
| MR-01 / **P0** | No frozen current candidate: 96 tracked files and 636 untracked paths; HEAD is the 2026-10-09 base. Historical release certification is not mapped to this worktree. | Engineering + Release owner | Review intended file set; resolve candidate scope; produce exact reproducible build/SBOM, test report, image/source hashes, and acceptance on one immutable candidate. No bulk staging or cleanup is assumed. |
| MR-02 / **P0** | All 43 current PostgreSQL inputs have disposable replay evidence, but the complete application schema is not established. The original 29-object inventory has 0 new SQL definitions. Six SC-001 objects are now superseded or excluded for the core workflow, and the three Cost Intelligence dependencies are route-excluded; their schemas remain unresolved. Twenty M0 candidates remain role-eligible without complete route-by-route database-contract acceptance. Hosted Supabase behavior and full authenticated browser acceptance remain unverified. | Database/migration owner + product/release owner + independent reviewer | Qualify every remaining role-eligible candidate's authoritative schema, ownership, grants, RLS, and functions or exclude it; reconcile the M0 catalogue's proposed/not-certified metadata; then replay and verify startup, rollback, route denial, and tenant isolation on a fresh isolated database. |
| MR-03 / **P0** | No single accepted hosted customer application journey. SQ-APP r5 lacked the required financial RPC and interactive login; separate CFO and recovery runs passed on different isolated targets. | Application + Identity + Product acceptance owners | On one authorized target, execute browser A/B login, workspace selection, evidence ingestion, CFO/Ask/decision/approvals/export, logout/re-auth, cross-tenant denials, and failure cases; map every test to the exact app image and database schema. |
| MR-04 / **P0** | No current service-side Supabase schema/RLS/migration or billing observation beyond user-supplied project status. | Supabase/database owner + Finance | Obtain the sanitized read-only evidence bundle described in the executive summary; compare each project against an approved target baseline and reconcile current itemized bill/credits before selecting any project for a role. |
| MR-05 / **P0** | Off-host recovery, RPO/RTO, key escrow, production scheduler/alerts, retention policy, and named recovery operator are absent or inactive. | Operations + Backup/Recovery + Product Owner | Owner accepts objectives (or replaces proposals); separately approve a bounded destination/cost; run and time an independent synthetic restore through authenticated workflow validation; prove key retrieval, alert delivery, retention/deletion, and resource inventory. |
| MR-06 / **P1** | Ask acceptance claims differ by document/version; universal query blocker and local certification are not linked to one current exact candidate. | Product + AI/Ask owner | Define the sellable bounded Ask contract and supported questions; record provider/runtime/model/config identity; validate unseen and adversarial prompts, evidence scope, provenance, UNKNOWN, and tenant denial on the release candidate. |
| MR-07 / **P1** | AWS financial publication requires D1–D8; no live CUR artifact/customer AWS access or hosted publisher acceptance is demonstrated. Azure discovery is explicitly blocked. | Security/Identity + Data Evidence + Cloud connector owners | Obtain signed decisions; implement the least-privilege authority and retained-source proof; then separately authorize and test one synthetic/non-production target before customer activation. |
| MR-08 / **P1** | G08 application route lacks accepted production operator, policy, evidence/fencing providers and application adapter; route returns 503 by design. | Identity/Security + Database + Application owners | Preserve current denial until providers, tenant binding, policy/revocation, atomic execution, receipt projection and app/browser tests are independently accepted. |
| MR-09 / **P1** | ECS task templates assign `SUPABASE_SERVICE_KEY` to frontend and several other task types; no cloud deployment proof exists. | Security + Platform owner | Reconcile task-level privilege requirements, eliminate unnecessary secret distribution, test build/runtime secret boundaries, and obtain security approval before any template use. |
| MR-10 / **P1** | No evidenced external pilot acceptance, published terms/privacy/support route, named service owner, or validated commercial price. | Product + Legal/Privacy + Support + Sales | Complete the external pilot checklist with customer-approved evidence, scope, outcome, data handling, support/escalation, commercial offer, and accountable owners. Pricing hypothesis is not a quote. |

## 5. Prioritized Execution Roadmap

This is a dependency-ordered roadmap, not a request to provision infrastructure now.

1. **Close the remaining M0 candidate route contracts.** Three legacy feature families are now route-excluded and the six SC-001 objects are classified for the core journey. Qualify or exclude the 20 remaining role-eligible candidates without inferring keys, joins, tenant rules, or product scope from callers.
2. **Freeze one sellable candidate.** Product and release owners define the bounded V1 customer journey; review the dirty worktree without discarding it; select exact files, repair release metadata, and produce a reproducible, provenance-bearing candidate. Resolve the service-key template issue and inconsistent Ask claims before certification.
3. **Close canonical data/auth integration locally.** On a fresh disposable PostgreSQL target, replay the reviewed complete V1 chain including the 43 inputs already qualified and the new authoritative application DDL. Verify Auth/RLS, role/function ownership, financial RPCs, evidence persistence, and upgrade/rollback results. Do not use any protected project as the test target.
4. **Run one integrated synthetic customer acceptance.** Using the exact candidate and one explicitly approved non-production target, test A and B through browser login, tenant-specific workspace/evidence, bounded Ask, decision/approval history, export, logout/re-authentication, negative authorization, and controlled dependency failure. Record exact hashes and test commands.
5. **Qualify operations and recovery before a paid pilot promise.** Set owner-approved recovery and availability objectives, obtain an all-in cost limit, name operators/key custodians, and execute a genuinely independent synthetic restore with full-service timing, alert receipt, and evidence retention. Keep deployment single-region/single-tenant initially unless measured demand requires otherwise.
6. **Accept commercial obligations and pilot outcome.** Obtain customer-approved scope/evidence, terms/privacy, support/escalation, price and success metrics. Only then make a separately approved hosting/activation decision. Keep G08 privileged operations deferred unless separately qualified.

### Next task

Inventory and qualify the database dependencies of the 20 remaining role-eligible M0 candidate routes, excluding routes whose authoritative contracts are not available. Reconcile the route catalogue's in-file "proposed" and `NOT_CURRENTLY_CERTIFIED` labels. Do not write DDL until source, keys, tenant semantics, ownership, grants, RLS, lifecycle, and canonical authority are evidenced.

### 2026-11-12 API contract closure checkpoint (pre-consolidation)

The current 29 missing literal-call objects are registered individually in
[the API object register](./nexora-v1-api-contract-closure-2026-11-12/API_OBJECT_REGISTER.md):
At that checkpoint, the objects were classified as 2 V1 REQUIRED
(`approval_history`, `approval_requests`), 1 V1 SUPPORTING
(`enterprise_data_fabric`), 19 DEFERRED and 7 UNKNOWN. Zero were resolved.
SC-001/SC-002 still block other database contracts and the other six required
objects. The route and approval consolidation below changes reachability but
does not add database definitions.

The targeted task run passed **65 tests, 0 failures, 0 skips** in 72.89 seconds.
Its fresh-cluster test covers the existing 43-input chain and separate
namespaced customer-workflow service contract; it does not establish the
29 legacy contracts or full application/browser acceptance. No SQL or
application code changed. **V1 DATABASE CONTRACT remains NO-GO.**

See the [implementation report](./nexora-v1-api-contract-closure-2026-11-12/IMPLEMENTATION_REPORT.md),
[security results](./nexora-v1-api-contract-closure-2026-11-12/SECURITY_TEST_RESULTS.md),
[application acceptance](./nexora-v1-api-contract-closure-2026-11-12/APPLICATION_ACCEPTANCE.md),
and [remaining blockers](./nexora-v1-api-contract-closure-2026-11-12/REMAINING_BLOCKERS.md).

### 2026-11-13 route and approval consolidation checkpoint

The Approval Center and Reports pages now route through the canonical
`CustomerWorkflowService`; its authenticated API preserves the Finance → CIO →
CEO sequence, append-only history, tenant scope, and evidence-linked export.
No `approval_requests` or `approval_history` DDL was added. The M0 route
catalogue is enforced in `app_main.py`; controlled-supporting and deferred
pages are not registered. Both FastAPI entry points omit legacy alerts,
recommendations, reports, governance, FinOps, and SaaS routers as applicable.
Legacy in-process background-job opt-in now fails closed in the V1 API.

The targeted approval, customer-workflow, G08, route, and job suite passed
**56 tests**. A broader run recorded **71 passed and 3 failed** in the
pre-existing production navigation assertions (client-admin persona expects
26 pages but declares 27, and its "Workspace" section is outside the test's
canonical section list); those assertions concern unchanged persona data.
Four PostgreSQL tests require the explicit `NEXORA_CUSTOMER_WORKFLOW_LOCAL_PG=1`
flag; the resulting opt-in disposable-cluster execution is recorded in the
route consolidation test report. The browser direct request to
`/cloud_connections` returned HTTP 404 while unauthenticated. No authenticated
browser journey or hosted Supabase verification was performed.

See the
[architecture decision](./nexora-v1-route-approval-consolidation-2026-11-12/ARCHITECTURE_DECISION.md),
[route matrix](./nexora-v1-route-approval-consolidation-2026-11-12/ROUTE_ENFORCEMENT_MATRIX.md),
[updated object register](./nexora-v1-route-approval-consolidation-2026-11-12/UPDATED_API_OBJECT_REGISTER.md),
[test results](./nexora-v1-route-approval-consolidation-2026-11-12/TEST_RESULTS.md),
and [remaining blockers](./nexora-v1-route-approval-consolidation-2026-11-12/REMAINING_BLOCKERS.md).
**V1 DATABASE CONTRACT and production activation remain NO-GO.**

## Sources inspected

- Product/release: [local certification](../production/NEXORA_FINAL_LOCAL_PRODUCT_CERTIFICATION.md); [release record](./NEXORA_V1_FINAL_RELEASE.md); [M0](./nexora-v1-m0-2026-11-07/M0_BASELINE.md), [M1](./nexora-v1-m1-2026-11-07/M1_EXECUTION_REPORT.md), [M2A](./nexora-v1-m2a-2026-11-07/M2A_IMPLEMENTATION_REPORT.md), [M2B](./nexora-v1-m2b-2026-11-07/M2B_IMPLEMENTATION_REPORT.md), [M2C](./nexora-v1-m2c-2026-11-08/M2C_IMPLEMENTATION_REPORT.md), [M3](./nexora-v1-m3-2026-11-10/M3_IMPLEMENTATION_REPORT.md); [universal Ask blocker](./UNIVERSAL_GOVERNED_ASK_BLOCKER.md); [Ask UAT defect](./ASK_NEXORA_UAT_DEFECT.md); [pilot checklist](../production/PILOT_ACCEPTANCE_CHECKLIST.md); [pilot criteria](../commercial/pilot/PILOT_SUCCESS_CRITERIA.md).
- Authentication and G08: [auth route](../../backend/routes/auth.py); [tenant contract](../../auth/authenticated_tenant.py); [G08 application reconciliation](./nexora-m4-g08-application-reconciliation-2026-11-11/REPORT.md); [canonical gateway](./nexora-m4-g08-canonical-sql-gateway-qualification-2026-11-11/qualification.md); [trusted execution](./nexora-m4-g08-trusted-execution-2026-11-11/qualification.md).
- Financial publication: [NXR-DASH-10](../cmp/NXR-DASH-10-implementation-results.md); [RC-01](../cmp/NXR-DASH-RC-01-staging-acceptance.md); [RC-02](../cmp/NXR-DASH-RC-02-local-acceptance.md); [M4 CFO integration](./nexora-m4-cfo-integration-2026-11-11/REPORT.md); [financial repository](../../repositories/aws_financial_evidence_repository.py); [dashboard adapter](../../services/aws_financial_dashboard_adapter.py); [semantic planner](../../enterprise_copilot/semantic_planner.py).
- Persistence/recovery: [V1 journey and recovery report](./nexora-v1-customer-journey-2026-11-12/qualification.md); [recovery package](../../scripts/postgres_recovery_package.py); [customer recovery verification](../../scripts/verify_customer_workflow_recovery.py); [independent-recovery package](../../deploy/operations/independent-recovery/README.md).
- Infrastructure/migrations/cost: [deployment architecture](../DEPLOYMENT_ARCHITECTURE.md); [ECS task templates](../../deploy/ecs/); [bootstrap manifest](../../deploy/production/bootstrap-manifest.json); [P6 blocker](../cmp/CMP-P6-DEF-001/REPORT.md); [Supabase migrations](../../supabase/migrations/); [SQL contracts](../../database/contracts/); [historical G07 evidence](../../deploy/staging/NXR-CLOSE-016/evidence/G07/); [cloud cost review](./nexora-v1-customer-journey-2026-11-12/previous-cloud-deployment-cost-review.md).
- API contract closure: [object register](./nexora-v1-api-contract-closure-2026-11-12/API_OBJECT_REGISTER.md); [implementation report](./nexora-v1-api-contract-closure-2026-11-12/IMPLEMENTATION_REPORT.md); [security results](./nexora-v1-api-contract-closure-2026-11-12/SECURITY_TEST_RESULTS.md); [application acceptance](./nexora-v1-api-contract-closure-2026-11-12/APPLICATION_ACCEPTANCE.md); [remaining blockers](./nexora-v1-api-contract-closure-2026-11-12/REMAINING_BLOCKERS.md).
- History: current session and checkpoints listed above; five older session context lookups returned empty transcripts; Git history through `3b4a1100` and the observed dirty worktree.

No product code, tests, migrations, deployment configuration, Supabase project, or protected resource was modified during this reconciliation. No cloud API operation, database write, provisioning, commit, tag, push, deployment, or G08 activation occurred.

### 2026-11-13 V1 route freeze and integrated customer acceptance

The runtime V1 route profile now freezes the 20 remaining M0 candidate routes
as **4 REQUIRED_V1, 0 OPTIONAL_V1, and 16 DEFERRED**. Customer Workspace is a
separate required workflow extension. Cost Intelligence, Dependency Analysis,
and Technology Digital Twin remain prior explicit exclusions. Enterprise
Registry is deferred; no service-role credential was exposed and no
unapproved backend reader was introduced. The route freeze is an enforcement
overlay only: the M0 catalogue still carries proposed /
`NOT_CURRENTLY_CERTIFIED` metadata.

An authenticated synthetic browser journey completed in one isolated
application, authentication, and PostgreSQL environment. It covered Customer
A workspace, evidence validation, grounded Ask, decision, distinct Finance →
CIO → CEO approvals, evidence-linked export creation, logout/reauthentication,
app restart, durable resume, and Customer B cross-tenant denial. The Approval
and Board Pack aliases were opened in-browser as `/approval_center` and
`/reports`. The export package and links were validated; the browser harness
did not capture a file-download event. The app container, not the database
container, was restarted.

Live PostgreSQL checks confirmed forced RLS on `events`, `evidence_objects`,
and `approvals`, a non-superuser/non-`BYPASSRLS` runtime role, five tenant
policies, and denial of Customer B's access to Customer A's workspace and of
JWT tenant-scope spoofing. FastAPI deferred-route tests are separate API-level
evidence; FastAPI was not part of the integrated browser Compose deployment.
The focused route/navigation/authentication/customer-workflow/recovery/
operations suite recorded **73 passed, 0 failed, 4 skipped**. Four local
PostgreSQL fixture cases were skipped because host cluster binaries were
unavailable in the Linux test container; the isolated integrated PostgreSQL
environment was checked live. G08 remains fail-closed and V1 background jobs
remain disabled.

**V1 ENGINEERING FREEZE: GO** for the local synthetic route profile and
workflow tested here. **Production activation remains NO-GO**: owner-approved
RPO/RTO, independent off-host recovery, key custody, production scheduling and
alerts, named operations ownership, hosted release acceptance, and broader
customer/commercial readiness remain unqualified. The separate report package
is in [the V1 engineering freeze evidence](./nexora-v1-engineering-freeze-2026-11-13/).
The next executable task is to obtain explicit approval for recovery
objectives and an independent synthetic destination, then execute a timed
full-service restore through authenticated workflow validation.
