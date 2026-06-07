import json
from .db import get_db, log_audit_event

def export_user_data(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log WHERE username = ?", (username,))
    logs = cursor.fetchall()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    data = {
        "user": user,
        "audit_logs": logs
    }
    conn.close()
    log_audit_event(username, "export_data", "User exported their data")
    return json.dumps(data, default=str)

