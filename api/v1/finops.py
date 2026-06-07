from fastapi import APIRouter, HTTPException
from backend.services.cost_service import fetch_cost_data

router = APIRouter()

@router.get('/cost-summary')
def get_cost_summary(tenant_id: str):
    resp = fetch_cost_data(tenant_id)
    if not resp:
        raise HTTPException(status_code=404, detail="No cost data found")
    return resp

@router.get('/recommendations')
def get_recommendations():
    # TODO: Integrate with recommendation service
    return {"recommendations": []}

@router.get('/anomalies')
def get_anomalies():
    # TODO: Integrate with anomaly detection service
    return {"anomalies": []}

