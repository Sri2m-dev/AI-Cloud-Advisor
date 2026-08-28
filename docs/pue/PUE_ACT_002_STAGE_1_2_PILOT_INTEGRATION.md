# PUE-ACT-002 - Stage 1/2 Prospect Pilot Integration

## Status and authority

PUE-ACT-002 is an additive, limited pilot surface. It does not replace the
accepted prospect intake, currency-resolution, prospect analysis, session
bridge, or executive workspace. The existing prospect analysis remains the
only authoritative result.

The pilot exposes at most two bounded views:

- Stage 1: **Governed Evidence Discovery** - which governed concepts are
  available, partial, absent, conflicted, or blocked.
- Stage 2: **Analysis Capability** - which registered analytical capabilities
  are available, partial, unsupported, unknown, or blocked, including bounded
  governance reasons.

No numerical analytical result, recommendation, natural-language answer,
entity, relationship, or normalized row value may be displayed by this
surface.

## Control and activation

Every render resolves the current ACT-C1 activation policy. With no applicable
configuration, the resolver returns Stage 0 and the pilot produces no panel,
heading, placeholder, or layout gap. A global kill switch also suppresses the
pilot immediately.

This integration deliberately caps visible behavior at Stage 2. A Stage 3 or
Stage 4 configuration cannot expose answers or route Ask Nexora questions
through this package. The pilot does not import or call the question router,
planning engine, aggregation executor, or answer composer.

Activation scope is constructed only from the capability assessment's evidence
scope. Application session values cannot enrich absent organization or tenant
identity. Prospect-only evidence therefore remains prospect-only.

## Artifact flow

The Analyze Environment page can locate three opaque, analysis-scoped runtime
artifacts:

1. `pue_pilot_context` - exact evidence scope plus prospect and shadow
   fingerprints.
2. `pue_shadow_analysis` - a completed PUE-C10 shadow result.
3. `pue_shadow_request` - an optional request that can produce the shadow
   result when it has not already run.

The page performs no profiling, semantic discovery, normalization, coverage
assessment, or calculation. The pilot service verifies:

- the current prospect analysis fingerprint;
- the complete PUE evidence scope;
- the exact shadow-result fingerprint;
- a usable capability assessment; and
- a current effective activation decision.

Mismatch or stale provenance fails closed. A shadow exception is isolated and
shown, only at an enabled Stage 1/2, as a safe unavailable message stating that
the current prospect analysis is unaffected.

Shadow requests are cached by exact evidence context, filename, content, mapping
decisions, and authorized row references. Restarting the Analyze Environment
journey clears all page-level pilot artifacts.

## Display contracts

The page receives an immutable `PuePilotViewModel`. The model contains labels,
states, bounded reason text, source/sheet/record lineage counts, mapping counts,
normalization-run counts, and fingerprints. It has no amount, answer, result, or
currency-amount field.

Examples of safe Stage 1 statements include:

- Technology service - Available
- Currency - Not evidenced
- Security risk - Not evidenced

Examples of safe Stage 2 statements include:

- Total cost - Blocked: currency evidence is not sufficiently governed.
- Resource inventory - Not supported.

The pilot may report 184 observed records while refusing to display or derive
`861828` when governed currency is absent.

## Telemetry and audit

Telemetry is bounded to registered counters for activation resolution, Stage 1
and Stage 2 views, shadow runs/reuse/failures, visible blocked capabilities, kill
switch suppression, and rollback. It contains no raw values or analytical
answers.

Visible panels emit registered activation-audit events:

- `PUE_EVIDENCE_SURFACED`
- `PUE_CAPABILITY_SURFACED`

The activation vocabulary also reserves visibility-suppression and shadow
failure events for operational persistence integration. ACT-002 remains
process-local and retention-bound like the certified shadow engine.

## Explicit non-goals

- No production Ask Nexora routing.
- No PUE numerical answer visibility.
- No confirmation or mapping UX.
- No change to prospect totals or currency governance.
- No authority promotion or comparison blending.
- No new production persistence.
- No Stage 3 or Stage 4 activation.

## Local runtime certification harness

ACT-002A provides a deliberately local acceptance harness. It is unavailable
unless `PUE_PILOT_DEV_MODE=true` and the application environment is not
production. It accepts only an explicit analysis and prospect, stages 0-2, a
maximum four-hour expiry, and either the labeled synthetic `legacy-184` fixture
or a forced safe-failure fixture. There is no global activation option.

The running prospect page publishes a development-only, non-sensitive active
scope handoff derived from the authoritative prospect `tenant_id`, `audit_id`,
and `analysis_timestamp`. The prospect tenant ID becomes the PUE prospect ID;
the analysis ID is a deterministic opaque fingerprint of those three governed
fields. Organization and tenant remain absent for prospect-only evidence.

With the development flag set in both the operator shell and Streamlit shell,
inspect the active scope with:

```powershell
python -m universal_evidence.pilot.dev_harness --show-active-scope
```

Then create or replace the local control file without copying or inventing IDs:

```powershell
python -m universal_evidence.pilot.dev_harness `
  --use-active-scope `
  --stage 2 `
  --expires-minutes 30
```

Use `--stage 0` for rollback, `--kill-switch` to exercise immediate panel
suppression, or `--fixture failure` to exercise the safe unavailable state.
The control file is ignored by Git and contains no customer evidence. The
synthetic fixture runs through the real PUE-C10 pipeline and deliberately has
184 cost observations with no currency. It does not alter the current prospect
analysis or claim its synthetic values came from the uploaded evidence.

Changing the control file does not require a browser reload. Use the
development-only **Apply local PUE pilot control** button on the active prospect
page. This triggers an in-session Streamlit rerun, preserving legitimate auth
and prospect state. A full browser reload creates a new Streamlit session under
the existing architecture and may require re-authentication/re-upload; ACT-002B
does not weaken or persist authentication to change that behavior.
