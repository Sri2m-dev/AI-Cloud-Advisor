import pytest

from data_fabric.foundation import TenantContext
from services.v1_approval_authority import ApprovalAuthorityError, InMemoryApprovalAuthority


def test_v1_approval_is_tenant_scoped_and_append_only():
    authority = InMemoryApprovalAuthority()
    context = TenantContext("org-a", "tenant-a")
    foreign = TenantContext("org-b", "tenant-b")
    request = authority.create_request(
        context,
        subject_id="resource-1",
        requested_action="remediate",
        requesting_actor="requester-1",
        reason="approved remediation",
        request_id="request-1",
    )

    assert authority.get_request(context, "request-1") == request
    assert authority.get_request(foreign, "request-1") is None
    assert authority.list_requests(foreign) == ()

    cio = authority.transition_request(
        context, "request-1", to_state="APPROVED", actor="approver-1", reason="finance approved"
    )
    assert cio.state == "PENDING"
    assert cio.workflow_stage == "CIO"
    approved = authority.transition_request(
        context, "request-1", to_state="APPROVED", actor="approver-2", reason="cio approved"
    )
    assert approved.workflow_stage == "CEO"
    approved = authority.transition_request(
        context, "request-1", to_state="APPROVED", actor="approver-3", reason="ceo approved"
    )
    assert approved.state == "APPROVED"
    history = authority.get_history(context, "request-1")
    assert len(history) == 3
    assert history[0].from_state == "PENDING"
    assert history[-1].to_state == "APPROVED"
    assert authority.get_history(foreign, "request-1") == ()


def test_v1_approval_rejects_invalid_transition_and_duplicate_identity():
    authority = InMemoryApprovalAuthority()
    context = TenantContext("org-a", "tenant-a")
    authority.create_request(
        context,
        subject_id="resource-1",
        requested_action="remediate",
        requesting_actor="requester-1",
        reason="reason",
        request_id="request-1",
    )
    with pytest.raises(ApprovalAuthorityError, match="invalid approval transition"):
        authority.transition_request(
            context, "request-1", to_state="COMPLETED", actor="actor", reason="invalid"
        )


def test_v1_approval_preserves_escalation_and_compatibility_id():
    authority = InMemoryApprovalAuthority()
    context = TenantContext("org-a", "tenant-a")
    request = authority.create_request(
        context, subject_id="resource-1", requested_action="remediate",
        requesting_actor="requester-1", reason="reason", request_id="request-1",
    )
    escalated = authority.transition_request(
        context, "request-1", to_state="ESCALATED", actor="finance-1",
        actor_role="finance", escalated_to="cio", reason="needs CIO attention",
    )
    assert escalated.state == "ESCALATED"
    assert escalated.escalated_to == "cio"
    assert request.compatibility_id == 1
    assert authority.get_history(context, "request-1")[0].action == "ESCALATE"
    with pytest.raises(ApprovalAuthorityError, match="already exists"):
        authority.create_request(
            context,
            subject_id="resource-1",
            requested_action="remediate",
            requesting_actor="requester-1",
            reason="reason",
            request_id="request-1",
        )
