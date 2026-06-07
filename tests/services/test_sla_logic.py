from services.approval_service import calculate_sla_status

def test_calculate_sla_status_ok():
    approval = {"created_at": "2026-05-19T00:00:00Z"}
    resp = calculate_sla_status(approval)
    assert resp.success
    assert resp.data == "OK"

