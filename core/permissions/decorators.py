from functools import wraps
from typing import Callable, Any
from core.permissions.permission_matrix import has_permission

class PermissionDenied(Exception):
    pass

def require_permission(action: str):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            user_role = kwargs.get("user_role")
            if not user_role or not has_permission(user_role, action):
                raise PermissionDenied(f"Role '{user_role}' lacks permission for '{action}'")
            return func(*args, **kwargs)
        return wrapper
    return decorator

