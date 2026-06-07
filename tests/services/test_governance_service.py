from backend.services.governance_service import get_governance_summary

def test_get_governance_summary_empty():
    resp = get_governance_summary('tenant1')
    assert isinstance(resp, dict)
    assert resp['tenant_id'] == 'tenant1'
    assert resp['anomaly_count'] == 0
    assert isinstance(resp['severity_distribution'], list)
    assert isinstance(resp['top_findings'], list)

