import json
import os

from uuid import NAMESPACE_DNS, uuid5

import pandas as pd
from openai import OpenAI
from supabase import create_client

from config import DEFAULT_ORG_ID
from shared.recommendation_schema import normalize_recommendation

from core.transformers import (
RECOMMENDATION_REQUIRED_FIELDS,
RECOMMENDATION_TYPE_MAP,
)

from utils.schema_validator import validate_schema
