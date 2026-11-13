# L01 - sanitized credential disposition

Status: EXTERNAL ACTION REQUIRED; no rotation/revocation is claimed.

Source: docs/release/KNOWN_LIMITATIONS.md identifies an archived environment file formerly present in Git history with non-placeholder PostgreSQL host/user/password settings. M1 did not retrieve historical values or open secret files. The later SU-513239 operator-reported reset/connectivity success does not establish complete rotation/reuse/log-review scope.

Authorized custodian must:

1. Identify the affected account/environment from existing restricted records; do not post credentials or connection strings.
2. Inventory credential reuse and dependent clients, jobs, secret stores and deployments.
3. Coordinate rotation/revocation under the approved operational procedure; preserve security/audit evidence.
4. Confirm old credentials no longer authenticate using separately authorized validation. Do not use restoration or customer systems as test targets.
5. Update dependent secret references and verify intended clients without logging values.
6. Review access logs for the relevant exposure window; record incidents/disposition.
7. Assess any dependent signing/encryption material without destroying retained-data decryptability; a key change is not an arbitrary deletion.
8. Return sanitized evidence: custodian, date/timezone, scope identifiers, change/ticket references, old-credential denial result, dependent-client result and log-review disposition. No secret values or raw logs.

Repository protections implemented: deny-by-default Docker source/resource context; key/env/local/runtime evidence exclusions; expanded Git ignore for local execution material and credential file types; path/content packaging inspection with redacted failures. These protections do not remove Git history or rotate credentials. No history rewrite is performed.
