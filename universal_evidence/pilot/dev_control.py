"""Session-local development controls for upload-backed PUE Stage 0/1/2."""

from __future__ import annotations

import os

from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    ScopeLevel,
)
from universal_evidence.pilot.admission import EvidencePilotAdmission

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
SESSION_STAGE_KEY = "pue_local_pilot_stage"
SESSION_KILL_SWITCH_KEY = "pue_local_pilot_kill_switch"
SESSION_SCOPE_KEY = "pue_local_pilot_scope_fingerprint"
ALLOWED_STAGES = frozenset(
    {
        ActivationStage.SHADOW_ONLY,
        ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
        ActivationStage.CAPABILITY_VISIBLE,
    }
)


def dev_control_enabled(environ=None) -> bool:
    """Require both explicit pilot opt-in and the literal development environment."""
    environ = os.environ if environ is None else environ
    enabled = str(environ.get("PUE_PILOT_DEV_MODE", "")).strip().lower()
    environment = str(environ.get("ENVIRONMENT", "")).strip().lower()
    return enabled in TRUE_VALUES and environment == "development"


def valid_upload_scope(admission) -> bool:
    """Accept only a canonical admission produced by the upload boundary."""
    return (
        isinstance(admission, EvidencePilotAdmission)
        and bool(admission.scope.analysis_id)
        and bool(admission.scope.prospect_id)
        and bool(admission.evidence_fingerprint)
        and admission.authority == "SHADOW / NON-AUTHORITATIVE"
    )


def apply_dev_control(
    admission,
    *,
    stage,
    kill_switch: bool,
    session_state,
    activation_service=None,
):
    """Apply presentation preference through ACT-C1 without creating evidence scope."""
    if not dev_control_enabled() or not valid_upload_scope(admission):
        clear_dev_control_state(session_state)
        return False
    try:
        stage = ActivationStage(int(stage))
    except (TypeError, ValueError) as exc:
        raise ValueError("development pilot stage must be 0, 1, or 2") from exc
    if stage not in ALLOWED_STAGES:
        raise ValueError("development pilot stage must be 0, 1, or 2")

    if activation_service is None:
        from universal_evidence.pilot.runtime import get_activation_service

        activation_service = get_activation_service()
    actor = _actor()
    scope = ActivationScope(
        ScopeLevel.ANALYSIS,
        organization_id=admission.scope.organization_id,
        tenant_id=admission.scope.tenant_id,
        prospect_id=admission.scope.prospect_id,
        analysis_id=admission.scope.analysis_id,
    )
    activation_service.configure(
        scope=scope,
        stage=stage,
        actor=actor,
        reason="session-local ACT-C2 development presentation control",
        expires_at=admission.expires_at,
    )
    activation_service.set_kill_switch(
        enabled=bool(kill_switch),
        actor=actor,
        reason="session-local ACT-C2 development kill-switch simulation",
    )
    session_state[SESSION_STAGE_KEY] = int(stage)
    session_state[SESSION_KILL_SWITCH_KEY] = bool(kill_switch)
    session_state[SESSION_SCOPE_KEY] = admission.fingerprint
    return True


def clear_dev_control_state(session_state) -> None:
    for key in (SESSION_STAGE_KEY, SESSION_KILL_SWITCH_KEY, SESSION_SCOPE_KEY):
        session_state.pop(key, None)


def render_dev_control(st, admission) -> bool:
    """Render the tiny local operator surface after canonical upload admission."""
    if not dev_control_enabled() or not valid_upload_scope(admission):
        clear_dev_control_state(st.session_state)
        return False
    if st.session_state.get(SESSION_SCOPE_KEY) not in {None, admission.fingerprint}:
        clear_dev_control_state(st.session_state)

    with st.container(border=True):
        st.caption("DEVELOPMENT ONLY")
        st.subheader("PUE Pilot Controls")
        stage_columns = st.columns(3)
        actions = (
            ("Shadow", ActivationStage.SHADOW_ONLY),
            ("Evidence Discovery", ActivationStage.EVIDENCE_DISCOVERY_VISIBLE),
            ("Capabilities", ActivationStage.CAPABILITY_VISIBLE),
        )
        for column, (label, stage) in zip(stage_columns, actions, strict=True):
            if column.button(label, key=f"pue_local_stage_{int(stage)}", use_container_width=True):
                apply_dev_control(
                    admission,
                    stage=stage,
                    kill_switch=False,
                    session_state=st.session_state,
                )
                st.rerun()
        if st.button(
            "Kill Switch",
            key="pue_local_kill_switch",
            type="secondary",
            use_container_width=True,
        ):
            apply_dev_control(
                admission,
                stage=st.session_state.get(SESSION_STAGE_KEY, 0),
                kill_switch=True,
                session_state=st.session_state,
            )
            st.rerun()
        selected = ActivationStage(st.session_state.get(SESSION_STAGE_KEY, 0)).name
        status = "KILL SWITCH ACTIVE" if st.session_state.get(SESSION_KILL_SWITCH_KEY) else selected
        st.caption(f"Current local presentation: {status}")
    return True


def _actor() -> ActivationActor:
    return ActivationActor(
        "local-pue-pilot-operator",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
        ),
    )
