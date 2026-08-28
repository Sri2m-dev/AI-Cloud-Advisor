# PUE-ACT-002B - Manual Pilot Runtime Context Reconciliation

## Root cause

The manual failure contained two separate lifecycle conditions.

First, Streamlit session state is the existing authority for the active login
and active prospect journey. An in-app rerun preserves that state. A full
browser refresh may establish a new Streamlit session; `init_session()` then
defaults authentication to false and the app routes to login. The encrypted
prospect repository retains the prospect tenant and analysis under retention,
but the application intentionally has no URL token, cookie, or persistent auth
credential that silently restores that analysis into a new session.

ACT-002B does not modify this authentication architecture. The supported manual
procedure uses an in-page Streamlit rerun, not browser refresh.

Second, the original ACT-002A commands used invented `analysis-runtime-cert`
and `prospect-runtime-cert` identifiers. The accepted `ProspectAnalysis`
contract does not contain fields with those names. Its authoritative identity
is:

- `tenant_id`: temporary prospect tenant identity;
- `audit_id`: governed audit identity for that prospect boundary; and
- `analysis_timestamp`: identity of the current persisted analysis version.

The runtime adapter now maps these without consulting filenames, organization
names, login tenant state, or caller overrides:

- PUE `prospect_id` = authoritative prospect `tenant_id`;
- PUE `analysis_id` = deterministic opaque fingerprint of `tenant_id`,
  `audit_id`, and `analysis_timestamp`;
- `organization_id` = absent;
- `tenant_id` = absent.

The last two absences preserve prospect-only evidence provenance. The uploaded
prospect must not become production-tenant scoped because a logged-in session
also contains an organization.

## Development-only scope handoff

When and only when `PUE_PILOT_DEV_MODE=true` outside production, the active
Analyze Environment prospect page writes `.streamlit/pue-pilot-active-scope.json`.
It contains the four PUE scope fields, the bounded prospect fingerprint, and an
explicit `AUTHORITATIVE_PROSPECT_ANALYSIS` source label. It contains no spend,
currency, source rows, authentication credential, or user secret and is ignored
by Git.

The command-line harness can read this handoff through `--use-active-scope`.
At page consumption time, the harness independently reconstructs the scope from
the current `ProspectAnalysis` and requires an exact four-field match. A wrong
analysis, prospect, organization, or tenant identifier fails closed before any
activation configuration or shadow artifact becomes visible.

Session state locates the current prospect object; it does not choose or enrich
PUE scope.

## Safe rerun procedure

After changing the local pilot control, use the development-only **Apply local
PUE pilot control** button. The button invokes `st.rerun()` inside the current
authenticated prospect session. Do not use browser refresh as an activation
mechanism.

The same analysis-scoped synthetic certification artifact is reused across
reruns and stage changes. Stage 0, expiry, mismatch, or invalid control clears
only artifacts marked as created by the dev harness. Existing prospect result,
authentication, and unrelated session state are not changed.

## Remaining limitation

This is a local certification mechanism, not session recovery or production
activation. If a full reload creates a new session, the user follows the normal
login/upload flow. Durable prospect resumption would require a separately
governed authentication and retention design and is outside ACT-002B.
