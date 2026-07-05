# Changelog

## v1.0.0-enterprise-foundation - 2026-07-05

### Added
- Enterprise Business Architecture pages for business units, capabilities, services, processes, and enterprise capability mapping.
- Shared Platform Framework for executive summaries, reconciliation, business context, AI narratives, evidence panels, certification banners, and portfolio summaries.
- Enterprise Financial Model for canonical allocation, reconciliation, variance, and business-to-technology financial lineage.
- Certification services for Executive and CIO workspaces.
- Technology Digital Twin and Knowledge Graph standardization for CIO intelligence workflows.
- Streamlit compatibility helpers for modern table and chart rendering.
- Platform service layer for formatting, reconciliation, evidence, certification, and narrative composition.

### Changed
- Standardized Executive, CIO, and Business Architecture workspaces around certification-grade evidence, reconciliation, and business context.
- Modernized CIO workspace table and chart rendering through compatibility wrappers.
- Improved sidebar navigation and business architecture entry points.
- Introduced service payload caching for analytical dashboards and canonical platform rollups.

### Performance
- Repository reads use Streamlit cache data patterns where available.
- Enterprise Financial Model cached at 300 seconds.
- Business Context base payload cached at 600 seconds.
- Analytical certification dashboards cached at 300 seconds.
- Risk & Governance analytical payload cached at 120 seconds with live approval queue detail.

### Validation
- Certified Executive, CIO, and Business Architecture pages compile successfully.
- 18 key Streamlit routes return 200 OK in local release validation.
- Approval actions and mutation paths remain uncached.

### Notes
- Local screenshot and generated twin JSON artifacts are excluded from release commits.
- CIO workspace remains provisionally certified pending future dashboard-level performance evidence.

