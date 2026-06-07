from pydantic import BaseModel, Field, validator
from typing import Optional, List

class ApprovalRequest(BaseModel):
    org_id: str = Field(...)
    user_id: str = Field(...)
    amount: Optional[float] = None
    reason: Optional[str] = None
    items: Optional[List[str]] = None

    @validator('org_id', 'user_id')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Must not be empty')
        return v

def validate_approval_request(payload: dict) -> ApprovalRequest:
    return ApprovalRequest(**payload)

