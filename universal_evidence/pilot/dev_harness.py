"""Explicitly enabled local-only ACT-002 runtime acceptance harness."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    ScopeLevel,
)
from universal_evidence.contracts import (
    EvidenceAnalysisContext,
    EvidenceRowReference,
    EvidenceSource,
)
from universal_evidence.governance import (
    ActorType,
    ConfirmationActor,
    ConfirmationService,
)
from universal_evidence.normalization import AuthorizedSourceValue
from universal_evidence.pilot.models import PilotAnalysisContext
from universal_evidence.profiling import profile_evidence
from universal_evidence.semantic import discover_semantics
from universal_evidence.shadow import NormalizationBinding, ShadowAnalysisInput

APPLICATION_ROOT = Path(__file__).resolve().parents[2]
CONTROL_PATH = APPLICATION_ROOT / ".streamlit" / "pue-pilot-dev.json"
ACTIVE_SCOPE_PATH = APPLICATION_ROOT / ".streamlit" / "pue-pilot-active-scope.json"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_APPLIED_CONTROL = None
_SHADOW_BY_SCOPE = {}


class DevHarnessError(RuntimeError):
    """Raised when unsafe or invalid local harness configuration is requested."""


@dataclass(frozen=True, slots=True)
class DevPilotControl:
    analysis_id: str
    prospect_id: str
    organization_id: str | None
    tenant_id: str | None
    stage: ActivationStage
    expires_at: datetime
    kill_switch: bool
    fixture: str
    scope_source: str
    evidence_fingerprint: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ActiveProspectPilotScope:
    analysis_id: str
    prospect_id: str
    organization_id: str | None
    tenant_id: str | None
    prospect_fingerprint: str
    scope_source: str
    evidence_fingerprint: str | None


def harness_enabled(environ=None):
    environ = environ or os.environ
    environment = str(
        environ.get("ENVIRONMENT", environ.get("CLOUD_ADVISOR_ENV", "development"))
    ).strip().lower()
    enabled = str(environ.get("PUE_PILOT_DEV_MODE", "")).strip().lower()
    return enabled in TRUE_VALUES and environment not in {"prod", "production"}


def load_control(path=CONTROL_PATH, *, now=None):
    if not harness_enabled():
        return None
    now = now or datetime.now(timezone.utc)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    stage_number = int(payload["stage"])
    if stage_number not in {0, 1, 2}:
        raise DevHarnessError("local pilot stage must be 0, 1, or 2")
    analysis_id = str(payload.get("analysis_id") or "").strip()
    prospect_id = str(payload.get("prospect_id") or "").strip()
    if not analysis_id or not prospect_id:
        raise DevHarnessError("analysis_id and prospect_id are required")
    expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    if expires_at.tzinfo is None:
        raise DevHarnessError("expiry must include a timezone")
    if expires_at <= now:
        raise DevHarnessError("local pilot control has expired")
    if expires_at > now + timedelta(hours=4):
        raise DevHarnessError("local pilot expiry cannot exceed four hours")
    fixture = str(payload.get("fixture") or "legacy-184")
    if fixture not in {"legacy-184", "failure"}:
        raise DevHarnessError("unsupported local certification fixture")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    from universal_evidence.activation.fingerprint import fingerprint

    return DevPilotControl(
        analysis_id,
        prospect_id,
        payload.get("organization_id"),
        payload.get("tenant_id"),
        ActivationStage(stage_number),
        expires_at,
        bool(payload.get("kill_switch", False)),
        fixture,
        str(payload.get("scope_source") or "PROSPECT_ANALYSIS"),
        payload.get("evidence_fingerprint"),
        fingerprint(canonical),
    )


def resolve_active_prospect_scope(prospect_analysis):
    """Adapt existing governed prospect identity into the PUE scope vocabulary."""
    tenant_id = str(getattr(prospect_analysis, "tenant_id", "") or "").strip()
    audit_id = str(getattr(prospect_analysis, "audit_id", "") or "").strip()
    timestamp = str(
        getattr(prospect_analysis, "analysis_timestamp", "") or ""
    ).strip()
    if not tenant_id or not audit_id or not timestamp:
        raise DevHarnessError("active prospect analysis identity is incomplete")
    from universal_evidence.activation.fingerprint import fingerprint
    from universal_evidence.pilot.runtime import PILOT_SERVICE

    analysis_identity = fingerprint(tenant_id, audit_id, timestamp)
    return ActiveProspectPilotScope(
        analysis_id="prospect-analysis-" + analysis_identity[:24],
        prospect_id=tenant_id,
        organization_id=None,
        tenant_id=None,
        prospect_fingerprint=PILOT_SERVICE.prospect_fingerprint(prospect_analysis),
        scope_source="PROSPECT_ANALYSIS",
        evidence_fingerprint=None,
    )


def publish_active_prospect_scope(
    prospect_analysis, *, path=ACTIVE_SCOPE_PATH
):
    if not harness_enabled():
        return None
    scope = resolve_active_prospect_scope(prospect_analysis)
    payload = {
        "analysis_id": scope.analysis_id,
        "prospect_id": scope.prospect_id,
        "organization_id": scope.organization_id,
        "tenant_id": scope.tenant_id,
        "prospect_fingerprint": scope.prospect_fingerprint,
        "scope_source": scope.scope_source,
        "evidence_fingerprint": scope.evidence_fingerprint,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return scope


def load_active_prospect_scope(path=ACTIVE_SCOPE_PATH):
    if not harness_enabled():
        raise DevHarnessError("PUE_PILOT_DEV_MODE must be enabled outside production")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("scope_source") not in {"PROSPECT_ANALYSIS", "UPLOAD_EVIDENCE"}:
        raise DevHarnessError("active pilot scope source is invalid")
    return ActiveProspectPilotScope(
        str(payload["analysis_id"]),
        str(payload["prospect_id"]),
        payload.get("organization_id"),
        payload.get("tenant_id"),
        str(payload["prospect_fingerprint"]),
        str(payload["scope_source"]),
        payload.get("evidence_fingerprint"),
    )


def publish_active_upload_scope(admission, *, path=ACTIVE_SCOPE_PATH):
    if not harness_enabled():
        return None
    scope = ActiveProspectPilotScope(
        admission.scope.analysis_id,
        admission.scope.prospect_id,
        admission.scope.organization_id,
        admission.scope.tenant_id,
        admission.fingerprint,
        "UPLOAD_EVIDENCE",
        admission.evidence_fingerprint,
    )
    payload = asdict(scope)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return scope


def publish_and_verify_active_upload_scope(admission, *, path=ACTIVE_SCOPE_PATH):
    """Publish through the live page boundary and prove the dev handoff exists."""
    path = Path(path).resolve()
    environment = str(
        os.environ.get("ENVIRONMENT", os.environ.get("CLOUD_ADVISOR_ENV", "development"))
    ).strip().lower()
    enabled = harness_enabled()
    _trace_upload_publication(
        pilot_enabled=enabled,
        environment=environment,
        scope_created=admission is not None,
        publication_called=enabled,
        publication_path=path,
        publication_result="SKIPPED" if not enabled else "STARTED",
    )
    if not enabled:
        return None
    scope = publish_active_upload_scope(admission, path=path)
    if scope is None or not path.is_file():
        _trace_upload_publication(
            pilot_enabled=True,
            environment=environment,
            scope_created=True,
            publication_called=True,
            publication_path=path,
            publication_result="MISSING_AFTER_WRITE",
        )
        raise DevHarnessError(
            "PUE pilot scope was created but active-scope publication did not complete."
        )
    _trace_upload_publication(
        pilot_enabled=True,
        environment=environment,
        scope_created=True,
        publication_called=True,
        publication_path=path,
        publication_result="SUCCESS",
    )
    return scope


def _trace_upload_publication(**values):
    details = " ".join(f"{key}={value}" for key, value in values.items())
    print(f"PUE PILOT TRACE: {details}", flush=True)


def clear_active_pilot_scope(*, path=ACTIVE_SCOPE_PATH):
    """Remove the local-only active handoff when its evidence is no longer current."""
    path = Path(path)
    if path.exists():
        path.unlink()


def bootstrap_dev_pilot_session(session_state, prospect_analysis, *, path=CONTROL_PATH):
    """Populate only locator state for an explicit local certification control."""
    global _APPLIED_CONTROL
    if not harness_enabled() or not Path(path).exists():
        _clear_dev_session(session_state)
        return False
    try:
        control = load_control(path)
        active_scope = resolve_active_prospect_scope(prospect_analysis)
    except (DevHarnessError, OSError, ValueError, json.JSONDecodeError):
        _clear_dev_session(session_state)
        return False
    if _scope_key(control) != _scope_key(active_scope):
        _clear_dev_session(session_state)
        return False
    from universal_evidence.pilot.runtime import ACTIVATION_SERVICE, PILOT_SERVICE

    if _APPLIED_CONTROL != control.fingerprint:
        scope = ActivationScope(
            ScopeLevel.ANALYSIS,
            organization_id=control.organization_id,
            tenant_id=control.tenant_id,
            prospect_id=control.prospect_id,
            analysis_id=control.analysis_id,
        )
        ACTIVATION_SERVICE.configure(
            scope=scope,
            stage=control.stage,
            actor=_activation_actor(),
            reason="time-limited local ACT-002 runtime certification",
            expires_at=control.expires_at,
        )
        ACTIVATION_SERVICE.set_kill_switch(
            enabled=control.kill_switch,
            actor=_activation_actor(),
            reason="local ACT-002 runtime certification control",
        )
        _APPLIED_CONTROL = control.fingerprint
    capability_scope = _capability_scope(control)
    if control.fixture == "failure":
        session_state["pue_shadow_analysis"] = None
        shadow_fingerprint = "local-forced-shadow-failure"
    else:
        shadow_key = (
            control.analysis_id,
            control.prospect_id,
            control.organization_id,
            control.tenant_id,
            control.fixture,
        )
        shadow = _SHADOW_BY_SCOPE.get(shadow_key)
        if shadow is None:
            request = _legacy_184_request(control)
            shadow = PILOT_SERVICE.run_or_reuse_shadow(request)
            if shadow is not None:
                _SHADOW_BY_SCOPE[shadow_key] = shadow
        if shadow is None:
            return False
        session_state["pue_shadow_analysis"] = shadow
        shadow_fingerprint = shadow.fingerprint
    session_state["pue_pilot_context"] = PilotAnalysisContext(
        capability_scope,
        PILOT_SERVICE.prospect_fingerprint(prospect_analysis),
        shadow_fingerprint,
    )
    session_state["pue_dev_harness_active"] = True
    return True


def bootstrap_dev_upload_pilot(admission, *, path=CONTROL_PATH):
    global _APPLIED_CONTROL
    if not harness_enabled() or not Path(path).exists():
        return False
    try:
        control = load_control(path)
    except (DevHarnessError, OSError, ValueError, json.JSONDecodeError):
        return False
    active = ActiveProspectPilotScope(
        admission.scope.analysis_id,
        admission.scope.prospect_id,
        admission.scope.organization_id,
        admission.scope.tenant_id,
        admission.fingerprint,
        "UPLOAD_EVIDENCE",
        admission.evidence_fingerprint,
    )
    if _scope_key(control) != _scope_key(active):
        return False
    if _APPLIED_CONTROL != control.fingerprint:
        _configure_control(control)
        _APPLIED_CONTROL = control.fingerprint
    return True


def _clear_dev_session(session_state):
    if not session_state.pop("pue_dev_harness_active", False):
        return
    session_state.pop("pue_pilot_context", None)
    session_state.pop("pue_shadow_analysis", None)
    session_state.pop("pue_shadow_request", None)


def _scope_key(scope):
    return (
        scope.analysis_id,
        scope.prospect_id,
        scope.organization_id,
        scope.tenant_id,
        scope.scope_source,
        scope.evidence_fingerprint,
    )


def write_control(
    *,
    analysis_id,
    prospect_id,
    stage,
    expires_minutes=30,
    organization_id=None,
    tenant_id=None,
    kill_switch=False,
    fixture="legacy-184",
    scope_source="PROSPECT_ANALYSIS",
    evidence_fingerprint=None,
    path=CONTROL_PATH,
):
    if not harness_enabled():
        raise DevHarnessError("PUE_PILOT_DEV_MODE must be enabled outside production")
    stage = int(stage)
    if stage not in {0, 1, 2}:
        raise DevHarnessError("local pilot stage must be 0, 1, or 2")
    if not analysis_id or not prospect_id:
        raise DevHarnessError("analysis_id and prospect_id are required")
    if not 1 <= int(expires_minutes) <= 240:
        raise DevHarnessError("expiry must be between 1 and 240 minutes")
    payload = {
        "analysis_id": analysis_id,
        "prospect_id": prospect_id,
        "organization_id": organization_id,
        "tenant_id": tenant_id,
        "stage": stage,
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(minutes=int(expires_minutes))
        ).isoformat(),
        "kill_switch": bool(kill_switch),
        "fixture": fixture,
        "scope_source": scope_source,
        "evidence_fingerprint": evidence_fingerprint,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _activation_actor():
    return ActivationActor(
        "local-pue-pilot-operator",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
        ),
    )


def _configure_control(control):
    from universal_evidence.pilot.runtime import ACTIVATION_SERVICE

    scope = ActivationScope(
        ScopeLevel.ANALYSIS,
        organization_id=control.organization_id,
        tenant_id=control.tenant_id,
        prospect_id=control.prospect_id,
        analysis_id=control.analysis_id,
    )
    ACTIVATION_SERVICE.configure(
        scope=scope,
        stage=control.stage,
        actor=_activation_actor(),
        reason="time-limited local ACT-002 runtime certification",
        expires_at=control.expires_at,
    )
    ACTIVATION_SERVICE.set_kill_switch(
        enabled=control.kill_switch,
        actor=_activation_actor(),
        reason="local ACT-002 runtime certification control",
    )


def _capability_scope(control):
    from universal_evidence.capability import CapabilityScope

    return CapabilityScope(
        control.analysis_id,
        control.prospect_id,
        control.organization_id,
        control.tenant_id,
    )


def _legacy_184_request(control):
    now = datetime.now(timezone.utc)
    context = EvidenceAnalysisContext(
        control.analysis_id,
        "local-certification-source",
        control.prospect_id,
        control.organization_id,
        control.tenant_id,
    )
    source = EvidenceSource(
        context,
        "synthetic:act-002a-legacy-184",
        now,
        control.expires_at,
    )
    values = ["4683"] * 183 + ["4869"]
    content = ("Cost\n" + "\n".join(values) + "\n").encode()
    profile = profile_evidence(source=source, filename="synthetic-legacy-184.csv", content=content)
    discovery = discover_semantics(profile)
    column = discovery.columns[0]
    governance = ConfirmationService(clock=lambda: now)
    actor = ConfirmationActor(
        "local-certification-reviewer",
        "local-certification@nexora.invalid",
        "finance",
        ActorType.HUMAN,
    )
    governance.request_confirmation(
        discovery, column.source_column_reference, "financial.cost.total"
    )
    governance.confirm_mapping(
        discovery,
        column.source_column_reference,
        "financial.cost.total",
        actor=actor,
    )
    mapping = governance.get_effective_mapping(column, actor=actor)
    rows = tuple(
        AuthorizedSourceValue(
            EvidenceRowReference(
                context,
                mapping.scope.file_id,
                mapping.scope.sheet_id,
                row_numbers=(number,),
            ),
            value,
        )
        for number, value in enumerate(values, start=2)
    )
    return ShadowAnalysisInput(
        source,
        "synthetic-legacy-184.csv",
        content,
        governance.repository,
        (NormalizationBinding(mapping, rows),),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-id")
    parser.add_argument("--prospect-id")
    parser.add_argument("--organization-id")
    parser.add_argument("--tenant-id")
    parser.add_argument("--use-active-scope", action="store_true")
    parser.add_argument("--show-active-scope", action="store_true")
    parser.add_argument("--stage", type=int, choices=(0, 1, 2))
    parser.add_argument("--expires-minutes", type=int, default=30)
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--fixture", choices=("legacy-184", "failure"), default="legacy-184")
    args = parser.parse_args(argv)
    if args.show_active_scope:
        active = load_active_prospect_scope()
        print(json.dumps(asdict(active), indent=2))
        return
    if args.stage is None:
        parser.error("--stage is required unless --show-active-scope is used")
    values = vars(args)
    values.pop("show_active_scope")
    use_active = values.pop("use_active_scope")
    if use_active:
        active = load_active_prospect_scope()
        values.update(
            analysis_id=active.analysis_id,
            prospect_id=active.prospect_id,
            organization_id=active.organization_id,
            tenant_id=active.tenant_id,
            scope_source=active.scope_source,
            evidence_fingerprint=active.evidence_fingerprint,
        )
    path = write_control(**values)
    control = load_control(path)
    print("Pilot configuration written")
    print(f"analysis_id: {control.analysis_id}")
    print(f"prospect_id: {control.prospect_id}")
    print(f"stage: {int(control.stage)}")
    print(f"expires: {control.expires_at.isoformat()}")
    print(f"control: {path}")


if __name__ == "__main__":
    main()
