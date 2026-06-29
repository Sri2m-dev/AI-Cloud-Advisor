from services import audit_service

def log_event(user_email, action, details=None, category="activity", org_id=None, target=None):
    """
    Log an audit event to the primary audit_events table.

    This module is retained for older imports; active writes are delegated to
    services.audit_service instead of the legacy audit_log table.
    :param user_email: Email of the user performing the action
    :param action: Action performed (e.g., 'login', 'logout', 'view_dashboard')
    :param details: Optional details (dict or str)
    :param category: Event category (activity, audit, approval, security, etc.)
    :param org_id: Organization ID (optional)
    :param target: Target entity (optional, e.g., 'aws_invoice')
    """

    event_details = {
        "category": category,
        "details": details or {},
    }

    try:
        return audit_service.log_event(
            event_type=str(action).upper(),
            user_id=user_email or "unknown",
            action=action,
            resource_type=category,
            resource_id=target or action,
            org_id=org_id,
            details=event_details,
            status="success",
        )
    except Exception as e:
        print(f"Audit log failed: {e}")
        return {"error": str(e)}

def log_approval_action(user_email, approval_id, action, details=None, org_id=None, target=None):
    """
    Log an approval workflow action.
    """
    return log_event(
        user_email=user_email,
        action=f"approval_{action}",
        details={"approval_id": approval_id, **(details or {})},
        category="approval",
        org_id=org_id,
        target=target
    )

def log_login(user_email, success=True, details=None, org_id=None):
    """
    Log a login attempt.
    """
    return log_event(
        user_email=user_email,
        action="login_success" if success else "login_failure",
        details=details,
        category="security",
        org_id=org_id
    )

