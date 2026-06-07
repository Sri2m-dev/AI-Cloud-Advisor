from fastapi import APIRouter, Query

from services import saas_service

router = APIRouter()

@router.get('/licenses')
def get_licenses(org_id: str | None = Query(None)):
    return saas_service.get_saas_license_utilization(org_id)

@router.get('/inactive-users')
def get_inactive_users(org_id: str | None = Query(None)):
    return saas_service.get_inactive_saas_users(org_id)


@router.get('/duplicates')
def get_duplicate_tools(org_id: str | None = Query(None)):
    return saas_service.get_duplicate_saas_tools(org_id)

@router.get('/renewals')
def get_renewals(org_id: str | None = Query(None)):
    return saas_service.get_renewal_forecasting(org_id)


@router.get('/vendor-cost-trends')
def get_vendor_cost_trends(org_id: str | None = Query(None)):
    return saas_service.get_vendor_cost_trends(org_id)
