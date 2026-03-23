# Placeholder for cost route logic
from fastapi import APIRouter
from backend.services.cost_service import fetch_cost_data

router = APIRouter()

@router.get("/cost")
def get_cost():
    return fetch_cost_data()
