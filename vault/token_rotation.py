from __future__ import annotations

from datetime import datetime, timedelta, timezone


class TokenRotation:
    @staticmethod
    def rotation_plan(authentication_type: str) -> dict[str, str | bool]:
        auth = str(authentication_type or "").lower()
        auto_refresh = "oauth" in auth or "token" in auth
        next_rotation = datetime.now(timezone.utc) + (timedelta(days=30) if auto_refresh else timedelta(days=90))
        return {
            "auto_refresh": auto_refresh,
            "rotation_policy": "30 days" if auto_refresh else "90 days",
            "next_rotation": next_rotation.isoformat(),
        }
