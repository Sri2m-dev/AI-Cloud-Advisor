"""
Centralized authentication service for all authentication-related data access.
"""
from data_access_layer import get_user_profile

def authenticate_user(email, password):
    # Example: wrap your authentication logic here
    return get_user_profile(email=email)

