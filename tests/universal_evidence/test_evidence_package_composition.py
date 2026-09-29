from data_fabric.contracts.enums import EntityType
from data_fabric.source_facts import (
    FactType,
    SourceFactInput,
)
from universal_evidence.pilot.evidence_package_composition import (
    compose_certified_package_source,
    source_fact_mapping,
)
from universal_evidence.pilot.reconciliation import (
    SourceIdentityObservation,
)

COMMON = {
    "file_id": "file-1",
    "organization_id": "org-1",
    "tenant_id": "tenant-1",
    "prospect_id": "prospect-1",
    "analysis_id": "analysis-1",
    "source_id": "source-1",
}


def test_inventory_composes_existing_fact_and_identity_contracts():
    result = compose_certified_package_source(
        source_type="inventory",
        rows=(
            {
                "ResourceId": "i-123",
                "ResourceType": "EC2",
                "AccountId": "111111111111",
                "Region": "ap-south-1",
                "Application": "Checkout",
                "Environment": "prod",
                "Owner": "Platform",
                "CostCenter": "CC100",
                "BU": "Retail",
            },
        ),
        **COMMON,
    )

    assert result.source_type == "inventory"
    assert len(result.source_facts) == 4
    assert all(isinstance(item, SourceFactInput) for item in result.source_facts)

    fact_types = {item.fact_type for item in result.source_facts}

    assert fact_types == {
        FactType.RESOURCE_IDENTITY,
        FactType.APPLICATION_MEMBERSHIP,
        FactType.APPLICATION_OWNER,
        FactType.COST_CENTER,
    }

    observation = result.identity_observations[0]

    assert isinstance(
        observation,
        SourceIdentityObservation,
    )
    assert observation.source_identifier == "i-123"
    assert observation.organization_id == "org-1"
    assert observation.tenant_id == "tenant-1"
    assert observation.normalized_attributes["AccountId"] == ("111111111111")
    assert observation.normalized_attributes["Application"] == ("Checkout")


def test_cost_composes_cloud_cost_without_inventing_currency_fact():
    result = compose_certified_package_source(
        source_type="cost",
        rows=(
            {
                "UsageAccountId": "111111111111",
                "ProductCode": "AmazonEC2",
                "ResourceId": "i-123",
                "UnblendedCost": "12.50",
                "Currency": "USD",
                "Tag_Application": "Checkout",
                "Tag_Environment": "prod",
                "Tag_CostCenter": "CC100",
            },
        ),
        **COMMON,
    )

    fact_types = {item.fact_type for item in result.source_facts}

    assert FactType.CLOUD_COST in fact_types
    assert len(result.source_facts) == 3

    observation = result.identity_observations[0]
    assert observation.entity_type is EntityType.CLOUD_RESOURCE
    assert observation.normalized_attributes["Currency"] == "USD"


def test_application_mapping_composes_dependency_and_owner():
    result = compose_certified_package_source(
        source_type="application_mapping",
        rows=(
            {
                "Application": "Checkout",
                "BusinessService": "Order Processing",
                "AccountId": "111111111111",
                "Criticality": "High",
                "OwnerEmail": "owner@example.invalid",
            },
        ),
        **COMMON,
    )

    fact_types = {item.fact_type for item in result.source_facts}

    assert fact_types == {
        FactType.APPLICATION_MEMBERSHIP,
        FactType.APPLICATION_OWNER,
        FactType.DEPENDENCY,
    }

    assert result.identity_observations[0].source_identifier == "Checkout"


def test_org_account_retains_identity_attributes():
    result = compose_certified_package_source(
        source_type="org",
        rows=(
            {
                "AccountId": "111111111111",
                "AccountName": "Production",
                "OrgUnit": "Retail",
                "Status": "ACTIVE",
            },
        ),
        **COMMON,
    )

    assert len(result.identity_observations) == 1

    observation = result.identity_observations[0]

    assert observation.source_identifier == "111111111111"
    assert observation.normalized_attributes["OrgUnit"] == "Retail"


def test_sourcefact_provenance_is_row_level():
    result = compose_certified_package_source(
        source_type="inventory",
        rows=(
            {
                "ResourceId": "i-123",
                "Application": "Checkout",
                "Owner": "Platform",
                "CostCenter": "CC100",
            },
        ),
        **COMMON,
    )

    assert result.source_facts

    for fact in result.source_facts:
        assert fact.evidence_reference == "file:file-1:row:1"
        assert fact.provenance == {
            "file_id": "file-1",
            "row": 1,
        }


def test_certified_mapping_is_bounded_to_existing_fact_types():
    mapping = source_fact_mapping("cost")

    assert mapping == {
        "UnblendedCost": FactType.CLOUD_COST,
        "Tag_Application": FactType.APPLICATION_MEMBERSHIP,
        "Tag_CostCenter": FactType.COST_CENTER,
    }

    assert "Currency" not in mapping
    assert "UsageAccountId" not in mapping
    assert "Tag_Environment" not in mapping


def test_unknown_source_type_fails_closed():
    try:
        source_fact_mapping("unknown")
    except ValueError as exc:
        assert "Unsupported certified package source type" in str(exc)
    else:
        raise AssertionError("unknown source type must fail closed")
