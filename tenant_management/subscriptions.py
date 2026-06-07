from typing import Dict, Any

class TenantSubscriptions:
    @staticmethod
    def get_subscription(tenant_id: str) -> Dict[str, Any]:
        # TODO: Return subscription info
        return {"tenant_id": tenant_id, "plan": "Starter", "status": "active"}

