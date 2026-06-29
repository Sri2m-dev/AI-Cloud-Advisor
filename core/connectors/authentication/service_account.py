from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceAccountAuth:
    principal: str
    credential_ref: str
    tenant_id: str = ""

    def masked(self) -> dict[str, str]:
        return {
            "type": "service_account",
            "principal": self.principal,
            "credential_ref": self.credential_ref,
            "tenant_id": self.tenant_id,
        }
