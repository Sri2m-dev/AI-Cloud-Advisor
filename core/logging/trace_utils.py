import uuid
from typing import Optional
from datetime import datetime

def generate_trace_id() -> str:
    return str(uuid.uuid4())

def generate_request_id() -> str:
    return str(uuid.uuid4())

def get_timestamp() -> str:
    return datetime.utcnow().isoformat()

