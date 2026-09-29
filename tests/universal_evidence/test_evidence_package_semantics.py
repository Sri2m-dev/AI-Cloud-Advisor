from universal_evidence.governance import ConfirmationService
from universal_evidence.pilot.evidence_package_semantics import (
    CERTIFIED_PACKAGE_SEMANTICS,
    certified_field_semantic,
    certified_semantic_profile,
    is_certified_field,
)


def _registry_concepts():
    return {definition.concept.concept_id for definition in ConfirmationService().registry.concepts}


def test_all_four_certified_source_types_exist():
    assert set(CERTIFIED_PACKAGE_SEMANTICS) == {
        "org",
        "inventory",
        "cost",
        "application_mapping",
    }


def test_every_certified_package_concept_exists_in_governance_registry():
    registry = _registry_concepts()

    configured = {
        concept for profile in CERTIFIED_PACKAGE_SEMANTICS.values() for concept in profile.values()
    }

    assert configured
    assert configured <= registry


def test_inventory_uses_canonical_existing_concepts():
    profile = certified_semantic_profile("inventory")

    assert profile["ResourceId"] == "resource.identifier"
    assert profile["ResourceType"] == "resource.type"
    assert profile["AccountId"] == "cloud.account"
    assert profile["Region"] == "cloud.region"
    assert profile["Application"] == "application.name"
    assert profile["Environment"] == "tagging.environment"
    assert profile["Owner"] == "ownership.owner"
    assert profile["CostCenter"] == "organization.cost_center"
    assert profile["BU"] == "organization.business_unit"


def test_cost_uses_canonical_financial_and_attribution_concepts():
    profile = certified_semantic_profile("cost")

    assert profile["UsageAccountId"] == "cloud.account"
    assert profile["ProductCode"] == "technology.service"
    assert profile["ResourceId"] == "resource.identifier"
    assert profile["UnblendedCost"] == "financial.cost.total"
    assert profile["Currency"] == "financial.currency"
    assert profile["Tag_Application"] == "application.name"
    assert profile["Tag_Environment"] == "tagging.environment"
    assert profile["Tag_CostCenter"] == "organization.cost_center"


def test_application_mapping_uses_existing_enterprise_concepts():
    profile = certified_semantic_profile("application_mapping")

    assert profile["Application"] == "application.name"
    assert profile["BusinessService"] == "business.service"
    assert profile["AccountId"] == "cloud.account"
    assert profile["OwnerEmail"] == "ownership.owner"


def test_org_uses_existing_cloud_and_organization_concepts():
    profile = certified_semantic_profile("org")

    assert profile["AccountId"] == "cloud.account"
    assert profile["OrgUnit"] == "organization.business_unit"


def test_unsupported_fields_remain_unmapped():
    unsupported = (
        ("org", "AccountName"),
        ("org", "Status"),
        ("org", "JoinedDate"),
        ("inventory", "State"),
        ("cost", "BillingPeriodStart"),
        ("cost", "UsageDate"),
        ("cost", "UsageType"),
        ("cost", "UsageAmount"),
        ("application_mapping", "Criticality"),
    )

    for source_type, field in unsupported:
        assert not is_certified_field(source_type, field)
        assert certified_field_semantic(source_type, field) is None


def test_exact_field_matching_only():
    assert is_certified_field("inventory", "ResourceId")
    assert not is_certified_field("inventory", "resourceid")
    assert not is_certified_field("inventory", "Resource ID")
    assert not is_certified_field("inventory", "UnknownField")


def test_unknown_source_and_version_fail_closed():
    assert dict(certified_semantic_profile("unknown")) == {}
    assert (
        dict(
            certified_semantic_profile(
                "inventory",
                package_version="999",
            )
        )
        == {}
    )


def test_field_resolution_preserves_certified_authority():
    semantic = certified_field_semantic(
        "application_mapping",
        "BusinessService",
    )

    assert semantic is not None
    assert semantic.semantic_concept_id == "business.service"
    assert semantic.authority == "CERTIFIED_PACKAGE_CONTRACT"


def test_profile_is_immutable():
    profile = certified_semantic_profile("inventory")

    try:
        profile["ResourceId"] = "something.else"
        mutated = True
    except TypeError:
        mutated = False

    assert not mutated
