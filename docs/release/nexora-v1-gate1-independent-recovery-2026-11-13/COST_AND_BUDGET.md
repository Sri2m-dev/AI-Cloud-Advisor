# Gate 1 Independent Recovery — Cost and Budget

Assessment date: 2026-11-13
Hard ceiling: **₹1,000 total**
Current cloud execution spend: **₹0** — no cloud resource was created,
modified, restored, or charged. The local PG17 compatibility test reused the
existing Docker image and created/removed only a temporary container; it did
not incur cloud charges.

## Decision

**BLOCKED — the exact incremental cost of using the fixed existing project
cannot be verified.** The local compatibility result does not estimate
Supabase or application/Auth charges. No new project is proposed. Current compute size,
account credits, billing window, added disk/storage, retained package size,
application/Auth hosting, tax treatment, and invoice terms are not verified.
The prior ₹1,000 ceiling remains a hard limit; public unit rates and a stale
historical estimate are not authorization quotes.

## Public Supabase price inputs

The official [Supabase pricing page](https://supabase.com/pricing), reviewed
2026-11-13, lists a Pro organization at **$25/month**, with $10/month of
compute credits covering one Micro instance; additional project compute is
charged separately. The official
[compute billing guide](https://supabase.com/docs/guides/platform/manage-your-usage/compute)
says compute is hourly and any partial hour is billed as a full hour. The
official [billing FAQ](https://supabase.com/docs/guides/platform/billing-faq)
describes additional projects as starting around $10/month on Micro compute.
The Pro pricing page lists 8 GB database disk, 100 GB file storage, 250 GB
egress, and daily backups retained for 7 days within plan quotas; overages and
optional add-ons are additional. PITR is listed at $100/month per 7 days of
retention; it is not included in the proposed one-time drill. If PITR is
required, its published base price alone is approximately ₹9,410.17 before
tax at the reference rate, so it cannot fit the ₹1,000 cap.

For conversion only, [X-Rates](https://www.x-rates.com/historical/?from=USD&amount=1&date=2026-11-13)
reported **USD 1 = ₹94.101672** at 03:37 UTC on 2026-11-13. This is a
reference rate, not a card/bank settlement rate. No account-specific tax
invoice was available. An 18% tax sensitivity below is illustrative only; it
is not a tax determination.

## Fixed-project cost evidence — not a quote

| Component | Available evidence | Cost conclusion |
|---|---|---|
| Existing project compute | The project is reported active and healthy. Its current compute tier, organization plan/credits, and current billing line are not in the supplied evidence. | Incremental compute charge cannot be established; do not assume it is zero because the project already exists. |
| Database disk and storage | The new V1 package artifact and exact uncompressed storage size are not retained. Existing project disk usage and any billed growth are not verified. | No exact marginal disk/storage cost. |
| Historical G07 estimate | An older provider UI estimate for a different restoration configuration was $9.68/month compute + $0.50/month disk = $10.18/month. At the recorded reference rate, that is ₹957.96 before tax; an illustrative 18% sensitivity is ₹1,130.39. | Stale estimate, not the current project's bill or a quote for this V1 drill. It cannot authorize use under the ₹1,000 ceiling. |
| Transfer and application/Auth | No V1 artifact transfer or app/Auth recovery has been performed; package size, egress, storage, and runtime SKU/window are unknown. | Exact incremental service cost cannot be calculated. |
| Taxes, FX, and minimums | No current account invoice, applicable tax quote, payment FX, or project-specific minimum-billing details were inspected. | The all-in cost cannot be certified. |

Supabase compute uses hourly billing with partial-hour rounding, but the
fixed project's current tier and billable interval are unknown. The notional
730-hour conversion is not an exact estimate for this existing project.
PITR is not part of the proposed logical package restore; its current state
and price impact are not refreshed by this assessment.

## Required costs not presently quotable

| Component | Current evidence | Missing to produce an exact all-in quote |
|---|---|---|
| PostgreSQL compute and disk | Public Supabase rates and the stale historical G07 estimate above. | Current project compute size; actual billable window; organization plan and remaining credits; restored DB size; disk/IOPS and storage-growth charges. |
| Application compute | Required to restore authenticated customer service, not just a database. | Selected provider/SKU, region, billable duration, network ingress, TLS, and shutdown behavior. Supabase project pricing does not host this Streamlit application. |
| Evidence/storage roots | Existing package is capped at 1 GiB and captures filesystem roots; no artifact size was retained. | Actual package and uncompressed storage size, destination storage service/volume, encryption and retention charges. |
| Transfer | Local-source upload is required; no upload was performed. | Actual artifact size, transfer path, any source/provider egress and destination ingress rates, retry/temporary-storage requirements. |
| Backups/retention | Pro daily backups are listed as 7 days; PITR is an optional paid add-on. | Whether the selected destination qualifies for included backups, retention period, and whether PITR or a separate immutable copy is required. |
| Authentication/secrets | Auth service state/settings/API keys and application keys are outside the qualified workflow package. | Approved Auth hosting/configuration, secret custody, key recovery, and any separate service charges. |
| Taxes and FX | A reference USD/INR rate is available; no billing profile or invoice quote was inspected. | Provider tax quote for the actual billing entity, taxes/withholding, card or bank FX spread, and settlement fees. |
| Minimum billing and cleanup | Supabase compute is hourly with full-hour rounding for partial hours. | Current project's exact billing behavior, any project/compute minimums, start/stop timestamps, and lingering storage charges. |

## Historical estimate is not a quote

The older recovery review's **$10.18/month** estimate is retained above as
historical context only. It is not a current-project incremental estimate and
omitted a full application/service, actual transfer, tax, invoice FX, and
verified billing minimums.

## Budget control

Do not treat the ₹1,000 ceiling as spending authorization. Before proceeding,
obtain an itemized, date-stamped marginal-cost estimate for the exact existing
project and billable window. Include database compute/disk growth,
application/Auth, storage, transfer/egress, retention, minimum billing, tax,
and exchange/settlement costs. The total including contingency must be at or
below ₹1,000. If any line remains unpriced, this fixed destination is not
ready for authorization.

## Final read-only preflight update

The catalog-only query package is prepared at
[SUPABASE_READONLY_PREFLIGHT.sql](./SUPABASE_READONLY_PREFLIGHT.sql), but no
remote query or other cloud operation was performed. No configured database
connection variables, linked project reference, `psql` executable, or
authorized read-only credential were available. DNS resolved the fixed
database hostname to an IPv6 address at 2026-11-13 06:01:04 UTC; that does not
verify database reachability or billing. The exact incremental cost remains
unverified and the ₹1,000 ceiling is not certified.

