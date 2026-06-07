import os
from dotenv import load_dotenv

load_dotenv(".env.dev")

DEFAULT_ORG_ID = os.getenv(
    "DEFAULT_ORG_ID",
    "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"
)

