from pydantic import BaseModel, Field
from typing import Optional

class OrganizationRequest(BaseModel):
    org_id: str = Field(...)
    name: str = Field(...)
    address: Optional[str]
    contact_email: Optional[str]

    @classmethod
    def validate_organization_request(cls, payload: dict) -> 'OrganizationRequest':
        return cls(**payload)

