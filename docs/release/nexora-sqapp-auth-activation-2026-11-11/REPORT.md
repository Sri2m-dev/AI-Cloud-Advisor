# NEXORA SQ-APP Auth activation and r5 deployment

**SQ-APP Phase 1: NO-GO.** The corrected r5 image is running in isolated
staging. A separately approved, fresh PostgreSQL 17.11 Auth target now supports
real synthetic-user authentication and the tested cross-tenant denials.
Phase 1 remains NO-GO because the CFO page's required tenant-scoped financial
RPC is absent from the identity-only Auth gateway, interactive browser login
was not executed, and actual application reconciliation has not been
qualified.

## A. Preserved baseline and incident disclosure

- Branch/HEAD: `program/nexora-production-activation` /
  `3b4a1100d86ef05dd915cf1734a2c4fa6581c299`. The worktree remains dirty and
  ahead of its base; no commit, tag, or push was created.
- r4 is currently healthy on its original application image
  `sha256:325b99b9c42d37b4e61b3cc7d22b64d53a36f218452e8450a55396f3b02f8ce3`.
  Its ingress is `127.0.0.1:18513`. Current API/frontend container IDs are
  recorded in [deployment-identity.json](./deployment-identity.json). They
  match the targeted-closure before-state inventory, all four r4 services are
  healthy, and the r4 evidence SQLite hash matches that inventory. No
  pre-incident data hash exists, so pre-incident data continuity is not claimed.
- **Restriction incident:** one Compose invocation omitted the explicit
  project name while using r5 environment files. Compose selected the r4
  project and briefly stopped/recreated its API and frontend with the wrong
  deployment configuration. They were restored using the original r4
  `references.env`, base Compose file, and explicit r4 project name. The
  current API/frontend container IDs differ from the prior ones. Their image
  digest and application/evidence/prospect/Redis volume identities are the
  r4 ones; no r4 volume was deleted. The “do not modify r4” restriction was
  therefore violated during recovery; r4 is not represented as untouched.
- The accepted SQ-DB PostgreSQL 17.11 image remains
  `docker.io/library/postgres@sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`.
  Its existing `nexora-m3sq-local-20261110_postgres_data` volume is present
  with its original creation time, and the database container is healthy.
  Qualified fixtures, evidence, release guards, and prior qualification
  artifacts were not rerun or modified. The r5 application uses its own
  SQLite-backed volumes and is not connected to SQ-DB.
- Port `8513` remains occupied; `18513` remains r4 ingress. r5 uses the
  separate loopback-only `127.0.0.1:18514`.

## B. Auth target and authorization

- The Product Owner explicitly approved the fresh follow-on Auth target,
  corrected GoTrue digest, and the synthetic organization/user creation and
  qualification operations. The exact target and permitted scope are in
  [auth-target-approval.json](./auth-target-approval.json).
- Current target: Compose project
  `nexora-sqapp-auth-local-pg17-20261111`, internal network
  `nexora-sqapp-auth-local-pg17-20261111_private`, and fresh identity volume
  `nexora-sqapp-auth-local-pg17-20261111_identity_db`. Its PostgreSQL,
  GoTrue, PostgREST, and private TLS gateway containers are healthy.
- Pinned images: PostgreSQL 17.11
  `sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`;
  GoTrue v2.197.0
  `sha256:839f529492d116b4e8b7777c953a27c381d34c15a744b1bcefde5eefaa1f9f9f`;
  PostgREST
  `sha256:c847127074bd26e1b8d3f7c0e6e01e5346f4b85dd34f5d699fd230af960827c0`;
  and Nginx
  `sha256:62223d644fa234c3a1cc785ee14242ec47a77364226f1c811d2f669f96dc2ac8`.
- Auth/database/PostgREST services have no host-published ports and run on
  the private network. No admin UI, public DNS, public ingress, customer data,
  production identity, or restoration resource was used. Synthetic identities,
  credentials, and signing material remain outside the repository. Signup is
  disabled after creating the two authorized test users.
- The earlier incompatible target
  `nexora-sqapp-auth-local-20261111` and its identity volume are preserved as
  historical resources and were not repurposed or deleted.

## C. Auth compatibility and real-auth result

- The first isolated Supabase Auth target was incompatible: its existing
  migration ledger and `auth.oauth_clients` schema disagreed with the pinned
  GoTrue migration sequence, and alternate search paths either failed a
  migration or resolved GoTrue's unqualified `users` table to the Nexora
  profile table. Those observations and the superseded target are retained in
  [auth-compatibility.json](./auth-compatibility.json).
- The approved fresh PostgreSQL 17.11 target allowed GoTrue to apply its
  migrations to a blank identity database. The Nexora organization/profile
  schema was initialized afterward. The current Auth integration is compatible
  with this local self-hosted Supabase Auth, PostgREST, and PostgreSQL stack.
- Two synthetic users, two organizations, two UID-bound profiles, and two
  active memberships exist. Both users authenticated through the real
  FastAPI/GoTrue flow with HTTP `200`. The API verified JWT signature, issuer,
  audience, expiry, subject, session, and active server-side organization
  membership. No fixture identity or mock provider was used.

## D. r5 image, startup, and ingress

- API and frontend run the corrected local image
  `nexora-sqapp-r5-auth-context-hotfix@sha256:e4732cdaba11eea2a7dbba1bc3a9ea9320c1239d073d12e013b48833c03f74da`.
  It is an offline incremental build from local parent image
  `sha256:e6264fb4e31c5456ed64c646b0956191b56ed561ffec911c780f20b473a1e1b4`,
  whose base candidate is
  `nexora-sqapp-candidate@sha256:954b857b9ec4e87d42add8d5f73dd82d2ca4e30bae15138430037483691f969d`.
  The deployed image includes `database/db.py`, the Supabase auth module, and
  the recorded session-client fixes. Exact incremental source-file hashes
  and current container IDs are in
  [deployment-identity.json](./deployment-identity.json). Deployed versions
  are FastAPI 0.136.3, Pydantic 2.13.4, Streamlit 1.57.0, supabase-py 2.30.0,
  and Uvicorn 0.47.0.
- The image was built locally with build networking disabled and not
  published. The base checkout was dirty and its full build-context hash was
  not captured; no clean-commit or hermetic-build claim is made. Credentials
  were not included in the incremental source context or image.
- r5 API, frontend, Redis, and Nginx are healthy. PostgreSQL/Auth/PostgREST,
  API, and Redis have no host-published ports. Ingress is
  `https://localhost:18514`, loopback-bound, and its certificate chain was
  verified against the private r5 CA. Revocation lookup was disabled because
  that local CA has no online revocation service.
- Final TLS route checks returned `200` for `/health`, `/`, and
  `/_stcore/health`; they returned `404` for `/rest/v1/users`,
  `/auth/v1/signup`, `/api/v1/auth/me`, `/docs`, `/openapi.json`, `/metrics`,
  and `/admin`. The API and Auth gateway were separately reachable only on
  private networks.
- Private API probes returned `401` for missing or invalid bearer tokens.
  The owner-operation route returns `503` because privileged execution is
  deliberately disabled; no service-role key or privileged operator exists.
- Streamlit's login screen rendered with the expected NEXORA title and
  Username/Password fields. The first AppTest failure was an RLS `42501`:
  organization resolution used the global anonymous client. The mounted
  `SUPABASE_ANON_KEY_FILE` was also not read by the login client, and the CFO
  composition selected a global anonymous financial client. These defects
  were corrected by loading the mounted key and passing the authenticated
  session client through organization and spend-service resolution; missing
  production session clients fail closed.
- The failing scenario was `AppTest.from_file("app_main.py")`, followed by
  selecting `pages/cfo_workspace.py` after authenticated workspace
  selection. The underlying first exception was
  `postgrest.exceptions.APIError` with sanitized error
  `PostgreSQL 42501: permission denied for table organizations`. Streamlit
  redacted its traceback. At the failure, the session was authenticated and
  had its `auth_client`; User A/User B each had exactly one authorized
  organization. The resolver incorrectly ignored that session client and
  queried through the anonymous client.
- After those fixes, real User A and User B AppTests authenticated and bound
  each session to its sole authorized organization. CFO workspace composition
  initializes `CanonicalOptimizationService`, which initializes the canonical
  repository. The next required read, RPC
  `tenant_cloud_financial_posture`, returned HTTP `404` from the approved
  identity-only Auth gateway, which intentionally does not expose that
  financial route. The remaining page failure is therefore an unavailable
  application-data dependency, not an AppTest-only success condition. AppTest
  did not pass CFO page rendering.
- The real browser rendered the login form at `https://localhost:18514/login`.
  Interactive login was **NOT EXECUTED**: the browser could not load synthetic
  credentials from the protected external secret location, and credentials
  were not copied into browser/tool inputs. AppTest results are not substituted
  for browser qualification.
- Worker services were not deployed; owner actions, protected execution, and
  scheduled execution remain disabled. The full V1 or M4 product journey is
  not claimed.

## E. Real authentication and tenant isolation

**Qualified for the tested local synthetic accounts.**

- User A and User B each logged in successfully; both tokens had valid
  signature, configured issuer/audience, expiry, subject, and session
  information. Each user's server-side membership resolved to exactly one
  organization.
- PostgREST/RLS returned each user's own organization/profile and no rows for
  the other organization. Cross-tenant API requests and forged organization
  identifiers were denied with `403`.
- Invalid and expired tokens were denied with `401`. Refresh returned `200`;
  logout returned `200`; replay of a logged-out token returned `401`;
  reauthentication succeeded and cross-tenant denial still held.
- An API JWT signing-material mismatch was found: the API had mounted the
  superseded Auth project's JWT secret. Only the r5 API was recreated after
  correcting the external `SUPABASE_AUTH_JWT_FILE` path to the approved PG17
  Auth target. Both real-user logins then succeeded through the API; authorized
  scope returned `200`, forged tenant headers returned `403`, and invalid
  bearer tokens returned `401`. The external environment-file fingerprint
  and exact secret file paths (not secret values) are recorded in
  [deployment-identity.json](./deployment-identity.json).
- The authoritative database has two Auth users, two organizations, two
  profiles, and two active memberships. Owner/privileged execution remained
  disabled; its attempted route returned `503`.

These results qualify the tested authentication and tenant-isolation paths;
they do not qualify application reconciliation, dashboard navigation, owner
authority, or the complete M4 journey.

## F. Application reconciliation

**Not run; not qualified.** The actual application workflow was not exercised
for acknowledged commit, lost acknowledgment, authoritative outcome lookup,
idempotent replay, unknown-outcome denial, or exactly-once evidence
persistence. The owner route remains closed with `503` because the G08 adapter
is unavailable; the approved scope excludes privileged owner operations.
SQ-DB qualification is not substituted for this application test.

## G. Evidence, failures, and remediation

- Current target/container/image/volume identities, local CA ingress results,
  database counts, and service health are in
  [deployment-identity.json](./deployment-identity.json) and
  [smoke-results.json](./smoke-results.json).
- The authorized CFO workspace AppTest caused one additive r5 evidence
  database schema change: `canonical_optimization_opportunities` was created
  with zero rows when the canonical optimization repository initialized.
  The existing audit/lifecycle tables remain empty, the migration ledger
  remains at one row, and SQLite integrity is `ok`. The evidence database
  SHA-256 changed from
  `277492bf5e9644e5acf0d62aa4ac7dcf9d133e6486751825176db829f69487ee` to
  `1b83f0c6875cb5c7e0c8abffef0012e3049872e406e6f3c3c007991a139727bf`;
  it is not represented as unchanged.
- Changed application files and reasons:
  `services/supabase_client.py` reads the mounted anon-key file;
  `services/enterprise_spend_composition.py` resolves organization and spend
  access through the authenticated session client and fails closed;
  `shared/executive_page.py` passes that session client into the service;
  `tests/security/test_streamlit_auth_isolation.py` adds regression coverage.
  `deploy/sq-app/Dockerfile.r5-auth-context-hotfix` captures the offline
  incremental build inputs. The external r5 Auth environment file was updated
  to point the JWT verifier at the approved PG17 Auth signing material.
- The image-focused stage passed **21 tests** (1 deselected); the final
  targeted auth, tenant-isolation, and closed-owner suite passed **63 tests**
  (1 deselected). These results do not qualify the missing finance RPC,
  browser workflow, or reconciliation.
- Browser qualification is **NOT EXECUTED**. Once the approved app-data
  dependency is available, a local operator should log in as synthetic User A,
  select only Organization A, verify authorized pages/data, log out, then log
  in as User B and verify only Organization B. Attempt the prohibited
  cross-tenant route and confirm denial with no foreign data; then verify
  logout, session expiration, and reauthentication.
- The r4 Compose project was briefly modified during the recovery incident
  described in section A. Its original image and volume identities are
  restored and healthy, but the container recreation restriction was breached.
- The base candidate's full build-context hash remains unavailable. The final
  incremental source-file hashes are recorded in
  [deployment-identity.json](./deployment-identity.json); no additional build
  was performed to close the base-image provenance gap.
- Application reconciliation, browser-level authenticated workflow, owner
  authority, workers, and the complete M4 journey remain unqualified.

## H. SQ-APP Phase 1 decision

**NO-GO.** Corrected r5 is deployed and healthy; real local Auth and tested
cross-tenant denials pass. The CFO workflow is blocked by the unavailable
tenant-scoped financial RPC, interactive browser login was not executed, and
application reconciliation was not run. Therefore Phase 1 acceptance is not
met.

## I. SQ-APP Phase 2 / M4 prerequisites

1. Provide and explicitly approve an isolated application-data backend/private
   route implementing the tenant-scoped `tenant_cloud_financial_posture` RPC.
   Do not route r5 to SQ-DB or widen the identity-only Auth gateway without
   separate authorization.
2. With the data dependency available, complete real-browser User A/User B
   login, workspace selection, authorized navigation, logout, expiration,
   reauthentication, and post-reauthentication tenant-denial checks.
3. Separately authorize and wire the application reconciliation adapter and
   authoritative outcome reader; then test acknowledged commit, lost
   acknowledgment, lookup, idempotent replay, unknown-outcome denial, and
   exactly-once evidence persistence.
4. Qualify evidence upload, analysis, Ask, decisions, trace/export, encrypted
   resume/recovery, and required worker journeys for M4.
5. Keep privileged owner operations, external authority, and fencing disabled
   until separately authorized and qualified.

No production/restoration access, customer data, public DNS, public ingress,
release-guard bypass, commit, tag, push, or destructive cleanup occurred.
