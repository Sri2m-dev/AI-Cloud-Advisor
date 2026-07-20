# Program G Planning Baseline Ratification

Status: Ratified planning baseline
Owner: Srikanth Mudaliar
Ratification date: 2026-07-20
Import baseline: `02bae6453deddb4aaf605b81dedd0d1ee11cba17`

## Decision

The preserved P5 package from `C:\Temp\Nexora-P5` is the authoritative Program G
planning baseline for work-package scope, dependencies, sequencing, increments,
delivery governance, risks, team responsibilities, and release planning.

Ratification does not activate a work package. WP-001 through WP-003 are closed.
WP-004 through WP-020 remain inactive until each receives an explicit,
package-specific owner authorization after its Definition of Ready is complete.

## Original artifact provenance

The following SHA-256 values were captured before import:

| Artifact | Original SHA-256 |
|---|---|
| `NEXORA_CAPABILITY_DEPENDENCY_MAP.md` | `FCAA8BCA779197ECC017AD2413BC916E73C8C363A5AD849A3674C5E714869726` |
| `NEXORA_IMPLEMENTATION_BLUEPRINT.md` | `BE5F6D214C9CA8666C46C61673B89F9F4868366081314DD6F775255B4BD3C2E1` |
| `NEXORA_IMPLEMENTATION_GOVERNANCE.md` | `59036C59B06C457033817AD8F01D49269A753F687793EFAFEE6FC79FAEAFBDD0` |
| `NEXORA_INCREMENT_PLAN.md` | `9864468FA26F05D36D5336548EC9122AD921DA01BA867E584B915AFE65845D3C` |
| `NEXORA_RELEASE_ROADMAP.md` | `89B55E03C0C1607A816F7D2BDA26A5A484DA50E747451059B14F53A20E5AF245` |
| `NEXORA_RISK_REGISTER.md` | `10938C48A46C6FBA6CC4B455F79B1E7F03912AEBED90A56EF2AC452539CC2C8F` |
| `NEXORA_TEAM_OPERATING_MODEL.md` | `74DCAF229162E7BDE10BF4EEB1272CABE19EC32716979D0A902E2912B49CEC1C` |
| `NEXORA_WORK_PACKAGE_CATALOG.md` | `FBBCA02BFF4718671B667FBAB26898DF693095D3F6E1505D0771663DC25DC43E` |

The imported documents change only stale governance metadata and two obsolete
pre-ratification statements. Their planning definitions otherwise remain intact.

## WP-004 gate

The catalog identifies WP-004 as **Connector evidence certification**, in
Increment 1, dependent on WP-002 and WP-003. Its detailed activation package
must still define explicit exclusions, component boundaries, acceptance tests,
evidence requirements, and any governing ADRs before owner activation.

No implementation branch, source change, schema change, migration, Supabase
operation, or runtime change is authorized by this ratification.
