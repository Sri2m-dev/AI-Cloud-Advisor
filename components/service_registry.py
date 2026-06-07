# components/service_registry.py
"""
Central service registry check for analytics functions and contracts.
Ensures all required analytics functions exist before dashboard load.
"""

import importlib
import sys

REQUIRED_ANALYTICS_FUNCTIONS = [
    "get_total_cloud_spend",
    "get_spend_by_cloud",
    "get_top_services",
    "get_governance_trends"
]

MISSING_FUNCTIONS = []

try:
    analytics_service = importlib.import_module("services.analytics_service")
    for func in REQUIRED_ANALYTICS_FUNCTIONS:
        if not hasattr(analytics_service, func):
            MISSING_FUNCTIONS.append(func)
except Exception as e:
    MISSING_FUNCTIONS = REQUIRED_ANALYTICS_FUNCTIONS


def check_service_registry():
    """
    Returns (bool, list): (all_ok, missing_functions)
    """
    return (len(MISSING_FUNCTIONS) == 0, MISSING_FUNCTIONS)

