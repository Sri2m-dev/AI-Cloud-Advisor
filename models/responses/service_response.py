from typing import Any, Optional, List
from pydantic import BaseModel

class ServiceResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    errors: Optional[List[str]] = None

