from typing import Dict, Any

class TenantConfig:
    @staticmethod
    def get_config(tenant_id: str) -> Dict[str, Any]:
        # TODO: Load tenant-specific config
        return {"tenant_id": tenant_id, "branding": "default", "plan": "Starter"}

