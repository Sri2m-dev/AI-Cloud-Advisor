from decimal import Decimal

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.financial_read_models import enterprise_spend_read_model


class Posture:
    has_data = True
    currency = "USD"
    total_ingested_spend = Decimal("120")
    cloud_spend = Decimal("120")
    source_rows = 1
    persisted_facts = 1
    evidence_references = ("fact-1",)


class SpendService:
    CONTRACT_VERSION = "test-v1"

    def get_financial_posture(self, context):
        return Posture()


def context():
    return AuthenticatedTenantContext(
        organization_id="11111111-1111-4111-8111-111111111111",
        organization_name="Org",
        user_id="user-1",
        user_email="user@example.com",
        role="finance",
        authorization_claims=frozenset(),
        tenant_id="11111111-1111-4111-8111-111111111111",
    )


def test_financial_read_model_preserves_p1_and_unknown_dimensions():
    result = enterprise_spend_read_model(context(), SpendService())
    assert result.total.value == Decimal("120")
    assert result.cloud.value == Decimal("120")
    assert result.total.authority == "P1:test-v1"
    assert result.total.provenance == ("fact-1",)
    assert result.saas.value is None
    assert result.saas.availability == "UNKNOWN"
