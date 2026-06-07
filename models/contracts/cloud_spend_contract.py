# models/contracts/cloud_spend_contract.py
"""
Contract definition for cloud spend analytics output.
Ensures schema consistency and prevents drift.
"""
from typing import TypedDict

class CloudSpendContract(TypedDict):
    cloud: str
    spend: float

