# NEXORA SQ-APP Phase 1 status

**Decision: NO-GO.** The isolated services are live, but there is no approved
test Auth tenant or real test identity. No authenticated login, cross-tenant
denial, effective database authorization, or complete Phase 1 journey is claimed.

## A. Source and image identity

- Docker context: `desktop-linux`.
- Branch: `program/nexora-production-activation`.
- HEAD: `3b4a1100d86ef05dd915cf1734a2c4fa6581c299`.
- The worktree was already dirty; the build was from a hashed allowlisted
  snapshot, not a clean commit. The r5 snapshot contains 1,331 application
  files and records the exact source and build-input hashes in
  [candidate-source-manifest-r5.json](./candidate-source-manifest-r5.json).
- The existing running services use application image
  `sha256:325b99b9c42d37b4e61b3cc7d22b64d53a36f218452e8450a55396f3b02f8ce3`.
  Its recorded source scan matched 1,330 files.
- A local-only corrected candidate was built, not published:
  `nexora-sqapp-candidate@sha256:b1ef17552bdc4061f2a118240aa4934e290619a330dc531e31aaedcbf35d1d43`.
  Python base: `sha256:83f339c1be6340ae1096010fdccf6552ac932d8f410d45d206014916bdf37e48`.
  The r5 image contains 1,331 files matching the build context, including
  `database/db.py`; the bounded path/content scan found no restricted paths or
  credential-pattern matches. See
  [image-qualification-r5.json](./image-qualification-r5.json).
- Pinned service images: Nginx
  `sha256:0dcc88822d45581e65ae329f8be769762bf628d3b2bb7d2a077d4aa5c98b30e3`;
  Redis `sha256:520775a41a63e77e06c73e35d2fd9cc15921a609516818796b4ecbb813078bc7`.
- The preserved SQ-DB report identifies PostgreSQL 17.11 image
  `sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`.
  SQ-DB fixtures, containers, and volumes were not changed or requalified.
- r5 dependency check passed (151 installed distributions). Verified versions:
  FastAPI 0.136.3, Streamlit 1.57.0, Uvicorn 0.47.0, Supabase 2.30.0,
  Redis 8.1.0, Celery 5.7.0, psycopg2-binary 2.9.11, PyJWT 2.13.0,
  httpx 0.28.1, cryptography 48.0.0.

## B. Target and authorization

- Existing isolated Compose project: `nexora-sqapp-local-20261110`.
- The application, evidence, prospect, and Redis volumes are separately named
  `nexora-sqapp-local-20261110_*` and labeled
  `nexora.scope=sqapp-synthetic-disposable`.
- SQ-DB remains a different project, network, and synthetic-disposable volume;
  its PostgreSQL port is unpublished. The application project does not attach
  to the SQ-DB network.
- The SQ-APP preflight records `SQ_APP_AUTH_TARGET_UNAVAILABLE`, zero accounts,
  no external egress, and no SQ-DB resource reuse. No approved identity tenant
  or authorization for creating one was available.

## C. Startup, health, and connectivity

- The existing r4 Nginx, frontend, API, and Redis containers were running and
  Docker-reported healthy at inspection. No existing container was stopped,
  recreated, or otherwise modified.
- Live, CA-verified loopback ingress returned `200` for `/health` and `/`.
  `/api`, login API, docs, OpenAPI, metrics, and readiness paths were not
  exposed by ingress (404). TLS terminated at the local reverse proxy.
- On the private application network, API liveness returned `200`, frontend
  health returned `200`, and protected readiness returned `503` with protected
  execution disabled. Missing and invalid bearer tokens returned `401`.
- The isolated r5 FastAPI process also started successfully with no network;
  `/health` returned `200` and `/ready` returned `503` with protected execution
  disabled. This was an image smoke test, not a deployment.
- Port `8513` remains occupied by the pre-existing application. Port `18513`
  was already bound to the existing SQ-APP ingress at the time of this check;
  no additional bind or replacement was attempted.
- SQ-APP config uses a disposable SQLite file on its application volume. It is
  not connected to the qualified PostgreSQL cluster, so PostgreSQL-backed
  application authorization remains untested. Background and scheduled jobs
  are disabled; no worker journey was started.

## D. Real authentication

**Blocked.** Auth provider configuration is absent and the startup result says
`auth=UNAVAILABLE`, `protected_execution=DISABLED`. The local login screen is
not evidence of authentication. No users, organizations, operator, credentials,
or successful login were created or simulated.

## E. Tenant isolation

**Not run.** Without real, independently authenticated Organization A and B
users, cross-tenant API and database denial, forged-organization rejection,
revocation, expiration, and operator-authority tests cannot establish tenant
isolation. Unauthenticated rejection is only a fail-closed check, not a
tenant-isolation result.

## F. Application reconciliation

**Blocked and fail-closed.** The unauthenticated startup explicitly denies the
unqualified reconciliation workflow. No acknowledged/lost-ack commit,
authoritative outcome lookup, idempotent replay, unknown-outcome denial, or
exactly-once persistence was exercised against the actual authenticated app.
External authority and fencing remain disabled.

## G. Application smoke evidence

- The existing r4 image's isolated Streamlit AppTest failed because the image
  omitted `database/db.py`; a successful HTTP response from `/` did not prove
  that the app page rendered.
- The narrow packaging fix adds only `database/db.py` to the allowlisted build
  context; it does not include SQ-DB fixtures. The rebuilt r5 candidate's
  network-isolated AppTest rendered the `NEXORA` login screen with no exceptions
  and no authenticated session, using only disposable SQLite under `/tmp`.
- A one-shot, network-isolated r5 FastAPI run started and shut down cleanly;
  liveness passed while protected readiness correctly remained unavailable.
- r5 was **not deployed**. The running containers remain on r4, and no browser
  login, organization selection, authorized navigation, logout, expiration,
  reauthentication, or post-reauth tenant test passed.
- Recorded live and isolated checks are summarized in
  [smoke-results-r5.json](./smoke-results-r5.json).

## H. Failed criteria and remediation

1. Approved Auth tenant and test-identity authorization are unavailable. Obtain
   explicit approval and tenant configuration; do not use production identity
   credentials or substitute fixture identities.
2. The running r4 frontend image is missing `database/db.py`. The r5 candidate
   fixes and tests that packaging defect, but activation requires an authorized
   deployment path that does not alter the existing containers.
3. The application uses isolated SQLite rather than the qualified PostgreSQL
   target. Decide and qualify the intended app database integration before
   claiming effective database authorization.

The pre-existing SQ-DB qualification artifacts and release guards remain
untouched. No cleanup, release-guard bypass, commit, tag, or push occurred.

## I. SQ-APP Phase 1 outcome

**NO-GO.** The success condition requires a running frontend/backend with real
authenticated test users and verified cross-tenant denial. Those prerequisites
and results are absent. This is not a full M4 product-journey acceptance.

## J. SQ-APP Phase 2 prerequisites

- Complete Phase 1 with an approved test Auth tenant, two isolated synthetic
  organizations/users, a separately authenticated operator, and proven API and
  database tenant enforcement.
- Deploy the corrected image only through a separately authorized isolated
  staging change; establish the intended database integration and protected
  reconciliation workflow first.
- Keep evidence upload, analysis, Ask, decisions, trace/export, encrypted
  resume, external authority, and fencing disabled until their Phase 2
  authorization, isolation, recovery, and evidence controls are qualified.
