"""
Centralized role-permission matrix for RBAC enforcement.
"""

ROLE_PERMISSIONS = {
    "super_admin": [
        "view_all_dashboards",
        "manage_users",
        "manage_billing",
        "approve_billing",
        "manage_licenses",
        "access_msp_governance",
        "access_approval_zone",
        "view_audit_logs",
        "edit_settings",
        # Add more as needed
    ],
    "leadership": [
        "view_all_dashboards",
        "approve_billing",
        "access_approval_zone",
        "view_audit_logs",
        # Add more as needed
    ],
    "operations": [
        "view_operations_dashboard",
        "access_approval_zone",
        "manage_licenses",
        "access_msp_governance",
        # Add more as needed
    ],
    "technical": [
        "view_technical_dashboard",
        "manage_licenses",
        # Add more as needed
    ],
}

