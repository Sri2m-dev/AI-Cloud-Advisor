# NEXORA V1 — Previous Cloud Deployment and Cost Review

Review date: 2026-11-12. This is a repository-evidence review and architecture
proposal only. No provider API, account, cloud environment, or deployment was
accessed. Existing projects and worktree contents were preserved. No production
qualification verdict is upgraded by this review.

## Executive findings

- The owner reports that a prior NEXORA cloud environment was tested and then
  shut down because costs became excessive. That is a user-provided operational
  fact; the repository contains no invoice or billing export that establishes
  the amount or confirms the current state of every prior resource.
- The repository archives evidence of a historical Supabase source project
  (`nexora-p3-validation`, PostgreSQL 17.6, region `ap-southeast-2`) and a
  separate restored project (`nexora-p3-validation-restoration`, PostgreSQL
  17.11, same region). The database-only restore was completed in October
  2026. A dated closeout explicitly says the recovery project is retained and
  deletion is not authorized. Its state now is unknown; neither project was
  contacted.
- A restore confirmation screen captured in the evidence archive estimates
  **$9.68/month additional compute + $0.50/month additional disk =
  $10.18/month** for a new recovery project using the same compute size and
  approximately 1.5x disk. This is a historical provider UI estimate, not
  actual spend, an invoice, an all-in price, a current quote, or a hard cap.
- The archived source and recovery projects are separate project IDs, but the
  same provider organization and region. No evidence proves their underlying
  host, control-plane, or regional failure-domain independence.
- AWS ECS/Fargate, ALB, Redis/ElastiCache, Celery, NGINX, and separate
  monitoring are present as architecture recommendations/task-definition
  templates. No Terraform/CloudFormation stack or provider deployment output
  was found to prove those resources were actually deployed.
- There is no supported total monthly operating-cost estimate, and no
  defensible demonstration that an independent cloud recovery drill can be
  completed within INR 1,000. Current destination, billing granularity,
  transfer, taxes, and resource prices are unknown.

## 1. Prior deployment inventory and evidence

### Historical resources with execution evidence

| Resource | Purpose and observed historical state | Evidence strength and current status |
|---|---|---|
| Supabase project `nexora-p3-validation` (`ageubmyosicypqqkdvox`) | Source staging database used for backup and the database-only recovery test. Archived project metadata reports `ACTIVE_HEALTHY`, region `ap-southeast-2`, PostgreSQL 17.6.1 / engine 17. A physical backup point is recorded as 2026-10-17 17:36:05 UTC. | Historical project metadata and archived provider screenshots are present in `deploy/staging/NXR-CLOSE-016/evidence/G07/`. The captured state is not current inventory; current shutdown/retention state is unknown. |
| Supabase project `nexora-p3-validation-restoration` (`uuqprdnqhbsmwubeqouw`) | Separate project restored from the source physical backup. The archived restore record reports completion at 2026-10-18 02:11:41 UTC and a healthy project; PostgreSQL 17.11. The check covered the database, not full application recovery. | The screenshot inventory verifies local screenshot hashes and visual attribution; provenance is user-supplied. The G07 closeout explicitly requires retaining this project and says deletion is not authorized. Current state unknown; preserve it. |
| Supabase database backups | Historical recovery point and restored database contents. The evidence records 10 Data Fabric tables, 235 relationship rows, and matching MD5 content fingerprints; this is not full content/behavior equivalence or RTO. PITR was reported disabled in the historical recovery record. | Historical evidence only. Current backup freshness, retention, PITR state, and actual backup-storage charges are not verified. |

The two historical projects are identified here so the owner can recognize
them; their presence in a local archive does not authorize access, a restore,
or cleanup. The same provider region is recorded for the restore, and no
private-network configuration or independent provider failure domain was
established. The source-to-recovery PostgreSQL minor-version difference
(17.6 to 17.11) was acknowledged, not certified as full behavioral
equivalence.

### Configurations that describe an intended architecture, not proof of deployment

| Artifact | Described resources | Deployment evidence assessment |
|---|---|---|
| [Deployment architecture](../../DEPLOYMENT_ARCHITECTURE.md) | Streamlit frontend, FastAPI, Celery worker and beat, Redis/ElastiCache, NGINX, ALB, ECS/Fargate, Supabase PostgreSQL/Auth, CloudWatch, Secrets Manager/SSM, Prometheus/Grafana. | Explicitly a recommended topology. Its “Next Hardening Steps” says service definitions/IaC, ALB health/autoscaling, and observability additions remain to be done. Not evidence of live resources. |
| [ECS task templates](../../../deploy/ecs/) | Five Fargate task-family JSON templates: frontend and API each request 0.5 vCPU/1 GiB; worker 0.5 vCPU/1 GiB; beat and NGINX 0.25 vCPU/0.5 GiB each. Combined template footprint is 2 vCPU/4 GiB if one of each ran continuously. | Image/account/region/Redis endpoints contain placeholders. Task definitions alone do not prove an ECS cluster, service, ALB, NAT, or Redis instance existed. |
| [Compose deployment](../../../docker-compose.deploy.yml) and [root Compose stack](../../../docker-compose.yml) | Local Compose services include frontend/API, Redis, worker/beat, NGINX, Prometheus/Grafana. | Local deployment recipe, not evidence that these ran in cloud. |
| [Telemetry Compose](../../../docker-compose.telemetry.yml) | Prometheus, Grafana, Loki, Promtail. | Local/optional telemetry configuration; no cloud-monitoring bill or ingestion volume recorded. |
| `deploy/operations/compose.yaml` | Guarded candidate stack; required persistent volumes and secret files are external managed inputs. | Local release candidate controls only. It is not a cloud deployment manifest. |

No `.tf` files or concrete CloudFormation templates/stacks were found in the
repository search. `execution/terraform_adapter.py` is application integration
code, not an infrastructure state file. No account-specific AWS/Azure/GCP
deployment identity, cloud bill, CUR export, Cost Management export, or invoice
was found in the reviewed evidence. Older release records explicitly defer
Supabase staging/Auth for external cost and defer live AWS/Azure certification
because a suitable non-production environment was not supplied:
[local certification](../../release/LOCAL_DEPLOYMENT_OPERATIONS_CERTIFICATION.md),
[integrated UAT status](../../release/INTEGRATED_BROWSER_UAT_STATUS.md).

## 2. Historical cost evidence: actual versus estimated

| Evidence | Amount | Classification | What it does not prove |
|---|---:|---|---|
| Supabase restore-to-new-project confirmation screenshot, archived 2026-10-18 | $9.68/month compute + $0.50/month disk = **$10.18/month additional** | Historical provider UI estimate for the shown restore configuration; same compute size as source and larger restore disk. | Not a posted charge, invoice, actual monthly bill, current price, tax-inclusive total, charge duration, or cost of all services. |
| Product Owner report in this task | “Costs became excessive” (amount not stated) | Owner-reported reason for shutdown. | No numeric spending history or resource-by-resource attribution. |
| Invoices, billing exports, cloud cost reports | None found in the reviewed repository evidence | **No actual historical spending figure available.** | Cannot quantify the former environment’s monthly spend or verify when every resource stopped billing. |

No currency conversion is applied. The USD screen estimate cannot establish the
INR 1,000 one-time limit without a current approved quote, exchange rate,
minimum billing period, taxes, storage/transfer/network charges, and resource
scope. Do not treat the estimate as a spending cap.

## 3. Likely excess infrastructure for current V1

For the qualified synthetic V1 journey—login, PostgreSQL-backed customer
workspace, evidence, bounded Ask, approvals, and exports—the following
architecture components appear optional unless a measured workload or product
requirement proves otherwise:

- **Always-on worker and Celery beat:** customer workflow operations are
  synchronous in the qualified path; no V1 requirement for a continuously
  running queue/scheduler was demonstrated.
- **Redis/ElastiCache:** not required for PostgreSQL persistence, tenant
  authorization, or synchronous approvals/exports. Do not keep it solely
  because Compose/task templates contain it.
- **Separate NGINX task plus ALB:** use one managed TLS ingress/reverse proxy
  layer, not a separately billed proxy tier plus a separate public balancer
  unless routing needs justify both.
- **Dedicated Prometheus, Grafana, Loki, and Promtail fleet:** use platform
  health checks, bounded-retention logs, and a small set of provider-native
  alerts for a small pilot. Add a dedicated metrics/logging service only with
  an operational requirement and priced ingestion/retention.
- **Autoscaling fleets, read replicas, multi-region duplicate services, and
  separate development/staging projects that remain running:** defer until
  load, availability, or isolation acceptance requires them. This is not a
  recommendation to delete any existing resource.
- **Unbounded AI/provider calls and live cloud connectors:** not necessary for
  the bounded synthetic V1 Ask/approval scope. Keep Ask deterministic and
  evidence-bounded for this pilot; external token usage/connectors are separate
  cost and permission gates.

The ECS template footprint above is a configured starting specification, not
evidence of actual running capacity or a cost estimate. Architecture reductions
must preserve TLS, tenant-bound authentication, PostgreSQL RLS/least privilege,
encryption, backup/recovery, and audit history.

## 4. Minimal secure V1 architecture proposals

### A. Temporary independent recovery qualification

```text
Synthetic source snapshot
  -> encrypted, checksummed package
  -> authenticated transfer over private path
  -> isolated temporary host in a separately approved failure domain
       - private-only network; no public PostgreSQL ingress
       - same PostgreSQL major version as package source
       - temporary superuser-equivalent restore identity
       - fresh database and restricted recovery storage
  -> separately configured synthetic verifier
  -> sanitized evidence copied out
  -> task-created temporary resources removed after approval
```

Keep the recovery target to one temporary PostgreSQL host/instance, one
restricted staging volume, and only the app/verifier process required for the
check. Do not add a public load balancer, Redis, workers, beat, replicas, or a
full observability stack for a one-time drill. Use host/provider logs with
short, owner-approved retention. Keep the backup encryption key separate from
the copied package and never put keys in command arguments.

The existing Supabase recovery project is a historical candidate only. It is
the same organization/region as the source, current state is unknown, and the
package restore contract needs global role creation and superuser-equivalent
privileges. Managed Supabase compatibility and independent failure-domain
separation have not been verified. Do not assume it can accept the current
complete package. The prior physical database-only Supabase restore is not the
same execution path as the current complete encrypted package.

**INR 1,000 conclusion:** cannot be demonstrated with repository evidence.
Reusing an existing independent, already-paid destination might reduce
incremental resource cost, but neither current availability nor its cost and
privileges are verified. A new small host could incur compute, disk,
network/egress, private networking, and billing-minimum charges; no provider,
region, rate, or run window is selected. Require a quote/zero-incremental-cost
proof that bounds the all-in spend under INR 1,000 before any new authorization.
Budget alerts are not hard caps.

### B. Minimal production pilot (proposal only)

```text
Browser
  -> managed HTTPS/TLS ingress
  -> one small, stateless V1 application deployment
       - authenticated UI and only required synchronous application endpoints
  -> one managed PostgreSQL/Auth project
       - Supabase Auth/JWT
       - organization-bound application roles, RLS, least privilege
       - encrypted workflow/evidence/approval/export records
  -> encrypted daily backup + separately retained off-host copy
  -> provider-native health/logging/alerting with bounded retention
```

Assumptions to validate before pilot approval: one region; one pilot tenant and
a bounded user count; one app replica for the smallest pilot (single-instance
availability is an explicit limitation); no asynchronous ingestion/scheduler;
no read replica; no LLM/provider connector use for bounded Ask; evidence size
caps enforced. Keep small encrypted evidence in PostgreSQL for the pilot if the
qualified application path supports the accepted size/volume. If evidence
requires object storage, use one private encrypted bucket with lifecycle and
backup policies and include its request, storage, and egress charges.

Do not expose PostgreSQL publicly. Prefer private app-to-database connectivity;
where the selected managed provider lacks a private path on the chosen tier,
require a reviewed TLS/network-allowlist design before approval rather than
opening `0.0.0.0/0`. Keep service-role/admin credentials backend-only in
managed secret custody. Enforce database tenant RLS independently of frontend
checks. Keep G08 disabled and fail-closed.

This is a low-complexity pilot proposal, not a high-availability commercial
SLA or production activation. A commercial service may require multiple app
instances, managed failover/PITR, stronger monitoring, support, and a tested
off-host recovery target; price and approve those separately before promising
availability.

## 5. Parametric monthly cost model

No current all-in price is supported by the evidence. Use the following model
with current provider calculator/quote inputs for the selected region and
plan; unknown input means the total remains **TBD**, not zero.

| Cost component | Explicit planning assumption | Monthly calculation/input needed | Current evidence |
|---|---|---|---|
| Application compute | One small app deployment; continuously available for pilot. The ECS template's frontend/API pair is 1 vCPU/2 GiB combined only as a sizing reference, not a selected product. | `730 × (vCPU-hour rate × vCPU + GiB-hour rate × GiB)` or provider's app-service quote. | No selected host/provider/rate. |
| Managed Auth/PostgreSQL compute | One project, one region, no replica. | Monthly selected tier price or `730 × DB instance hourly rate`. | Historical recovery-project UI estimate: $9.68/month additional compute at that past configuration; not current. |
| Database disk and backups/PITR | Size from measured data; retain backups per approved policy. | Provisioned GB-month + backup/PITR GB-month + I/O or backup operations. | Historical restore screen estimates $0.50/month additional disk; no actual usage, retention, or PITR cost. Historical record says PITR disabled then. |
| Evidence storage | Small bounded encrypted evidence in DB; otherwise one private object store. | DB/object GB-month + requests + replication/lifecycle + retrieval/egress. | No measured pilot volume or current rate. |
| Network/ingress/egress | One managed TLS ingress; private DB path; no NAT unless required. | Load balancer/private endpoint/NAT hours + data transfer. | No deployed network inventory or traffic totals. |
| Logs/monitoring | Provider-native health checks, alerts, and bounded log retention; no separate Grafana/Loki fleet. | Ingested GB × rate + retained GB-month + alert/metric add-ons. | No actual ingestion, retention, or bill. |
| Auth email/SMS/domain/secrets | Email-only/password auth unless product needs other channels; managed secret references. | Messages, domain, secret versions/requests, and provider-plan charges. | No selected plan or volume. |
| External AI/connectors | Zero for deterministic bounded Ask and offline synthetic V1. | Add only if explicitly enabled: tokens/API calls and connector egress. | Not included in minimal pilot. |
| **Total** | 730-hour month for continuously available services; usage variables to be measured. | **Sum of quoted line items, taxes, and any minimum commitments.** | **TBD.** $10.18/month historical restore estimate is only two line items, not the total. |

The model deliberately avoids estimating unknown provider prices from resource
names. A quote must capture SKU, region, minimum billing duration, storage,
backup retention/PITR, traffic, private networking, logs, tax, and exchange
rate. Add a service-level owner-reviewed monthly cap and hard operational
shutdown/run-duration controls; do not rely on budget-alert notification as a
hard spending limit.

## 6. Cost drivers and shutdown/retention controls

- **Compute uptime:** keep only the application service continuously running
  for pilot hours; no idle worker/beat/Redis. For a temporary drill, record
  the maximum billable window and stop only task-created compute after
  evidence is secured and the owner approves cleanup.
- **Managed database floor:** managed project compute and disk may remain
  chargeable while an application is stopped. A stopped/suspended project may
  retain disk, backup, or restore charges. Confirm provider billing semantics
  from the selected plan; do not assume pause means zero cost.
- **Recovery and backup copies:** retention, PITR, snapshots, off-host object
  storage, encryption operations, egress, and restored-project disk can all
  accrue charges. Choose a retention period only after product/legal approval;
  enforce lifecycle/deletion with evidence and preserve existing recovery
  artifacts until explicitly authorized.
- **Network:** avoid unnecessary public ALBs, NAT gateways, static IPs, and
  cross-region transfer. Keep PostgreSQL private; price required private
  connectivity instead of weakening security to avoid its cost.
- **Observability:** prefer bounded provider-native logs/health alerts. Set
  volume/retention limits and alert thresholds; avoid always-on multi-service
  monitoring where not required.
- **Shutdown sequence:** stop/scale app and optional jobs; verify customer
  access is intentionally offline; preserve database, backup, keys, and
  evidence per retention requirements; remove only explicitly approved
  task-created disposable networking/storage/compute. Reconcile resource IDs
  and bills after provider usage reporting. Do not delete the historical
  source or recovery projects under this review.

## 7. Exact prerequisites before spending

1. Owner identifies which historical Supabase project (if any) remains
   approved for read-only inspection, or supplies an approved provider,
   account/project alias, resource ID, and region. Current credentials and
   permissions are not inferred from archived artifacts.
2. Owner explicitly authorizes read-only state, topology, PostgreSQL version,
   private connectivity, and billing-plan inspection. This review itself made
   no provider API calls.
3. Confirm package compatibility: same PostgreSQL major as the backup;
   compatible `pg_dump`/`pg_restore`; dedicated target; supported role/global
   privileges; encrypted storage; no name collisions. Managed-provider
   superuser limitations must be checked before transfer or restore.
4. Confirm failure-domain separation and private access, and record a resource
   inventory with exact project/host/storage/network identities.
5. Obtain an all-in estimate for the exact run window, transfer, storage,
   networking, retention, monitoring, taxes, and minimum billing. Keep it
   below INR 1,000 with a documented margin. If not demonstrable, do not spend.
6. Separately authorize the external write steps (transfer and restore) and
   any provisioning. The prior preparation approval did not authorize them.
7. Agree synthetic-only inputs, restore-validation evidence, named operator,
   cleanup owner, evidence retention, and teardown authorization. Preserve
   existing historical resources unless separately authorized by exact ID.

## Updated Gate 1 blocker

Historical recovery project references are now identified from archived
evidence, but this does not remove the Gate 1 block. They are dated, same-region
Supabase projects; current status, private networking, failure-domain
separation, restore privileges, and cost are unverified. The current task
explicitly prohibits connecting to them. The repository's $10.18/month figure
is a historical restore estimate, not proof of an INR 1,000 bounded drill.
**Gate 1 remains BLOCKED; independent recovery and production readiness remain
NO-GO.**

See the updated [Gate 1 preflight checklist](./gate1-existing-environment-preflight.md)
and current [V1 qualification report](./qualification.md).
