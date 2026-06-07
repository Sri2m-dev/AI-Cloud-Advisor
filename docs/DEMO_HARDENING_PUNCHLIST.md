# Demo Hardening Punch List

Date: 2026-05-13
Scope validated from active app routing in [app.py](app.py).

## Active Demo Surface

- [app.py](app.py) routes to:
- [views/landing_page.py](views/landing_page.py)
- [views/onboarding.py](views/onboarding.py)
- [views/cto_dashboard.py](views/cto_dashboard.py)

All files above currently compile with no editor diagnostics.

## P0 (Must Fix Before External Demos)

1. Remove hardcoded Supabase service key from UI code
- Evidence: [views/cto_dashboard.py](views/cto_dashboard.py#L33)
- Why this is a blocker: leaked privileged credentials can invalidate trust during pilots/investor reviews.
- Fix: move URL/key to environment-backed configuration and rotate exposed key.

2. Eliminate silent fallback paths for config/history reads
- Evidence: [backend/services/alerting_engine.py](backend/services/alerting_engine.py#L57), [backend/services/report_service.py](backend/services/report_service.py#L165)
- Why this is a blocker: failures can look like healthy empty state during demo, masking operational issues.
- Fix: log structured errors and surface controlled warning banners with recovery guidance.

## P1 (High Demo-Trust Risk)

1. Raw HTML is heavily embedded in customer-facing pages
- Evidence: [views/landing_page.py](views/landing_page.py#L53), [views/onboarding.py](views/onboarding.py#L38), [views/cto_dashboard.py](views/cto_dashboard.py#L585)
- Why this matters: fragile rendering and inconsistent behavior across Streamlit updates can produce visible defects.
- Fix: keep CSS injection centralized, replace inline HTML blocks with native Streamlit components where possible.

2. No-data states lack recovery actions in core dashboard panels
- Evidence: [views/cto_dashboard.py](views/cto_dashboard.py#L1856), [views/cto_dashboard.py](views/cto_dashboard.py#L1917), [views/cto_dashboard.py](views/cto_dashboard.py#L2112)
- Why this matters: panels can feel empty or broken if source tables are missing.
- Fix: replace passive info text with guided empty states and CTA buttons.

3. Report/alert storage dependency messaging appears in main flow
- Evidence: [views/cto_dashboard.py](views/cto_dashboard.py#L1319)
- Why this matters: messaging implies incomplete setup during a live walkthrough.
- Fix: preflight-check dependencies before demo and switch to operator-friendly fallback language.

## P2 (Quality and Story Polish)

1. Replace placeholder-ish operations copy in recommendation workflow
- Evidence: [views/cto_dashboard.py](views/cto_dashboard.py#L1586), [views/cto_dashboard.py](views/cto_dashboard.py#L1609)
- Why this matters: failure copy is technical and internal-facing.
- Fix: map technical errors to concise executive-safe copy.

2. Convert remaining onboarding HTML progress UI to componentized rendering
- Evidence: [views/onboarding.py](views/onboarding.py#L38)
- Why this matters: improves maintainability and lowers rendering brittleness.

## Demo Gate Checklist (Freeze Rules)

- No broken controls across Landing -> Onboarding -> CTO Dashboard.
- No privileged secrets in frontend code.
- No raw exception text shown to audience.
- No empty panels without next-step CTA.
- No setup warnings during standard demo path.
- Last sync timestamp visible and believable on all KPI-led views.

## 48-Hour Hardening Plan

1. Day 1 AM
- Secrets extraction + key rotation.
- Add structured error logging in report/alert services.

2. Day 1 PM
- Add actionable empty states in dashboard no-data branches.
- Replace operator/internal warning copy in UI.

3. Day 2 AM
- Reduce raw HTML footprint in landing/onboarding and centralize style usage.

4. Day 2 PM
- Run full demo script rehearsal twice on a clean session.
- Sign off only if all demo gates pass.
