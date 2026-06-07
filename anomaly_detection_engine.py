import pandas as pd
import uuid
import os
import re

from datetime import datetime, timezone
from dotenv import load_dotenv
from postgrest.exceptions import APIError

from core.transformers import (
ANOMALY_REQUIRED_FIELDS,
ANOMALY_TYPE_MAP,
)

from utils.schema_validator import validate_schema

from services.supabase_client import supabase
