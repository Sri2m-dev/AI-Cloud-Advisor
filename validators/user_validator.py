from pydantic import BaseModel, Field, validator
from typing import Optional

class UserRequest(BaseModel):
    user_id: str = Field(...)
    email: str
    name: Optional[str] = None
    role: Optional[str] = None

    @validator('user_id')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('user_id must not be empty')
        return v

    @validator('email')
    def valid_email(cls, v):
        if not v or "@" not in v or "." not in v.rsplit("@", 1)[-1]:
            raise ValueError('email must be valid')
        return v

def validate_user_request(payload: dict) -> UserRequest:
    return UserRequest(**payload)

