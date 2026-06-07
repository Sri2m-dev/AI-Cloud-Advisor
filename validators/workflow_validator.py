from pydantic import BaseModel, Field
from typing import Optional, List

class WorkflowRequest(BaseModel):
    workflow_id: str = Field(...)
    steps: List[str]
    owner_id: str = Field(...)
    status: Optional[str] = None

    @classmethod
    def validate_workflow_request(cls, payload: dict) -> 'WorkflowRequest':
        return cls(**payload)

