# v1.3.0 Enterprise Classification Engine Baseline

Status: Certified

Release tag: `v1.3.0-enterprise-classification-engine`

Annotated tag object: `4f51ca18752e9dfa42d6e901872eec62d4eb2fc6`

Authoritative commit: `07525c351b8722a3b27b866f5f8b03cafdc27ecd`

Certification date: 2026-08-10

This directory records the immutable P4.2 release boundary used to start P4.3. The
release tag, local `main`, and `origin/main` were independently resolved to the same
commit before certification. The tagged tree contains 1,805 tracked files.

## Certification result

`P4_3_0_BASELINE_CERTIFIED`

| Gate | Result |
| --- | --- |
| Tag peeled commit | Exact match |
| `main` / `origin/main` | Exact match |
| Linked migration ledger | 17 local = 17 remote |
| Full suite | 818 passed, 2 skipped |
| P3 gate | 94 passed |
| PVT-003 | 60 passed, 2 skipped |
| Governance/certification | 40 passed; both scripts passed |
| Ruff | Passed |
| Compile/import | Passed |
| `pip check` | Passed |
| `git diff --check` | Passed |
| Hosted CI | Passed, run `31368283257` |
| Manual browser certification | Passed for all seven personas |

The two PVT/full-suite skips are the expected environment-gated cases. The full run
also reported existing dependency deprecation warnings; no test failed.

## Baseline contents

- [Architecture and canonical model](architecture.md)
- [RBAC and runtime composition](runtime-and-security.md)
- [Migration history](migrations.md)
- [Release notes](release-notes.md)

The tracked local runtime database is not release evidence and is intentionally excluded
from commits. No P4.3 feature implementation is included in this checkpoint.
