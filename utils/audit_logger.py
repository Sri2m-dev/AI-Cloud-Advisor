from datetime import datetime
from services.supabase_client import supabase

def log_event(user_email, action, details=None, category="activity", org_id=None, target=None):
    """
    Log an audit event to the audit_log table in Supabase.
    :param user_email: Email of the user performing the action
    :param action: Action performed (e.g., 'login', 'logout', 'view_dashboard')
    :param details: Optional details (dict or str)
    :param category: Event category (activity, audit, approval, security, etc.)
    :param org_id: Organization ID (optional)
    :param target: Target entity (optional, e.g., 'aws_invoice')
    """
    timestamp = datetime.utcnow().isoformat()
    data = {
        "user_email": user_email,
        "action": action,
        "details": details or "",
        "timestamp": timestamp,
        "category": category
    }
    if org_id:
        data["org_id"] = org_id
    if target:
        data["target"] = target
    try:
        supabase.table("audit_log").insert(data).execute()
    except Exception as e:
        print(f"Audit log failed: {e}")

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

