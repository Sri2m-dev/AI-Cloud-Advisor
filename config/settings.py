"""
Central configuration for environment, Supabase, feature flags, and license settings.
"""
import os
from dotenv import load_dotenv


load_dotenv()
load_dotenv(".env.dev", override=False)

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT") or os.getenv("CLOUD_ADVISOR_ENV", "development")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)

# Feature Flags
FEATURE_FLAGS = {
    "ENABLE_BILLING": os.getenv("ENABLE_BILLING", "false").lower() == "true",
    "ENABLE_AUDIT_LOGS": os.getenv("ENABLE_AUDIT_LOGS", "true").lower() == "true",
    # Add more feature flags as needed
}

# License Config
LICENSE_TYPE = os.getenv("CLOUD_ADVISOR_LICENSE", "community")
LICENSE_KEY = os.getenv("CLOUD_ADVISOR_LICENSE_KEY", "")

# Add additional centralized config as needed

