def delete_user_data(username):
    from .db import get_db, log_audit_event
    conn = get_db()
    cursor = conn.cursor()
    # Delete user-specific data
    cursor.execute("DELETE FROM audit_log WHERE username = ?", (username,))
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    log_audit_event(username, "delete_user_data", "User requested data deletion")
    conn.close()

