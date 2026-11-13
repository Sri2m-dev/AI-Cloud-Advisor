# NEXORA M4 CFO financial integration — accepted baseline

**Result: GO** for the isolated r5 CFO financial-data scope.

The deployed application uses image digest
`sha256:e217236489d4dd16e7390c27bf42d01cfb654a53ba268c91bc48749c9d14fc20`.
The isolated PostgreSQL 17/PostgREST project
`nexora-sqapp-data-r5-financial-20261111` applied canonical financial migrations
S001–S020; all 20 ordered artifact hashes matched and execution was verified.
S021–S027 and G08 privileged operations were not authorized by that financial
scope and were not applied.

## Qualification

- Focused Python suite: 95 passed. Image test stages: auth regression 21 passed,
  1 deselected; financial client 6 passed. Ruff passed for the changed Python
  integration and test files.
- Real Chrome login, workspace selection, CFO rendering, logout, and
  reauthentication passed for synthetic User A and User B. The canonical RPC
  returned tenant-specific totals of 1250.5 USD and 2345.67 USD respectively.
- Cross-tenant and raw-table requests were denied (403); anonymous, invalid,
  forged, and expired tokens were denied (401); wrong issuer was denied (403).
  Empty-period and controlled backend-error behavior passed.
- The database/PostgREST network was internal with no published database ports.
  r5 HTTPS was loopback-bound. r4 (5/5), SQ-DB (9/9), and Auth (4/4) container
  identities, image IDs, states, and network addresses matched the original
  inventory. Only the authorized r5 API/frontend were replaced; two financial
  target services were added.

Sanitized evidence:

- [Financial acceptance](./evidence/financial-acceptance-postdeploy.json)
- [Interactive browser qualification](./evidence/browser-qualification.json)
- [Migration verification](./evidence/migration-verification.json)
- [Database authorization checks](./evidence/database-security-verification.json)
- [CFO failure handling](./evidence/cfo-error-handling.json)
- [Resource preservation](./evidence/resource-preservation-verification.json)

No credentials, JWTs, private keys, or environment files are included.
G08 application reconciliation was not part of this GO.
