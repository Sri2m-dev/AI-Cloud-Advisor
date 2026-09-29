from data_fabric.contracts import EntityType
from data_fabric.foundation import TenantContext
from data_fabric.identity import InMemoryIdentityResolver
from data_fabric.registry import (
    InMemoryEntityRegistry,
    InMemoryRelationshipRegistry,
)
from enterprise_registry.canonical import enterprise_entity_from_source
from enterprise_registry.canonical_service import EnterpriseRegistryService
from universal_evidence.pilot.evidence_package_runtime import (
    CertifiedPackageSource,
    execute_certified_package_runtime,
)

ORG = "org-package"
TENANT = "tenant-package"
PROSPECT = "prospect-package"
ANALYSIS = "analysis-package"
PACKAGE = "EVD-PACKAGE-1"


def _registry():
    context = TenantContext(ORG, TENANT)

    return EnterpriseRegistryService(
        context,
        role="operations",
        entities=InMemoryEntityRegistry(),
        identities=InMemoryIdentityResolver(),
        relationships=InMemoryRelationshipRegistry(),
    )


def _entity(
    registry,
    entity_type,
    name,
    source_system,
    source_id,
):
    context = TenantContext(ORG, TENANT)

    entity = enterprise_entity_from_source(
        context=context,
        entity_type=entity_type,
        source_system=source_system,
        source_entity_id=source_id,
        canonical_name=name,
    )

    entity.metadata["act006"] = {"prospect_id": PROSPECT}

    return registry.register_entity(entity)


def _sources():
    return (
        CertifiedPackageSource(
            source_type="org",
            file_id="org_accounts.csv",
            rows=(
                {
                    "AccountId": "111111111111",
                    "AccountName": "Retail Production",
                    "OrgUnit": "Retail",
                    "Status": "ACTIVE",
                },
            ),
            mapping_decision_ids=("map-org",),
        ),
        CertifiedPackageSource(
            source_type="inventory",
            file_id="inventory.csv",
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
                {
                    "ResourceId": "i-inventory-only",
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
            mapping_decision_ids=("map-inventory",),
        ),
        CertifiedPackageSource(
            source_type="cost",
            file_id="cost_export.csv",
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
                {
                    "UsageAccountId": "999999999999",
                    "ProductCode": "AmazonEC2",
                    "ResourceId": "i-cost-only",
                    "UnblendedCost": "7.25",
                    "Currency": "USD",
                    "Tag_Application": "",
                    "Tag_Environment": "prod",
                    "Tag_CostCenter": "",
                },
            ),
            mapping_decision_ids=("map-cost",),
            normalization_references=("norm-cost",),
        ),
        CertifiedPackageSource(
            source_type="application_mapping",
            file_id="app_mapping.csv",
            rows=(
                {
                    "Application": "Checkout",
                    "BusinessService": "Order Processing",
                    "AccountId": "111111111111",
                    "Criticality": "High",
                    "OwnerEmail": "owner@example.invalid",
                },
            ),
            mapping_decision_ids=("map-app",),
        ),
    )


def test_real_package_publishes_existing_sourcefact_contract(
    tmp_path,
):
    registry = _registry()

    _entity(
        registry,
        EntityType.CLOUD_ACCOUNT,
        "111111111111",
        "certified_evidence_package",
        "111111111111",
    )
    _entity(
        registry,
        EntityType.CLOUD_RESOURCE,
        "i-123",
        "certified_evidence_package",
        "i-123",
    )
    _entity(
        registry,
        EntityType.CLOUD_RESOURCE,
        "i-inventory-only",
        "certified_evidence_package",
        "i-inventory-only",
    )
    _entity(
        registry,
        EntityType.APPLICATION,
        "Checkout",
        "certified_evidence_package",
        "Checkout",
    )

    result = execute_certified_package_runtime(
        package_id=PACKAGE,
        sources=_sources(),
        organization_id=ORG,
        tenant_id=TENANT,
        prospect_id=PROSPECT,
        analysis_id=ANALYSIS,
        source_fact_database=tmp_path / "facts.db",
        registry=registry,
    )

    assert {item.source_type for item in result.publications} == {
        "org",
        "inventory",
        "cost",
        "application_mapping",
    }

    assert sum(item.input_fact_count for item in result.publications) > 0

    assert sum(item.published_fact_count for item in result.publications) > 0

    facts = result.source_fact_service.repository.list_current_facts(ORG, TENANT)

    assert facts

    assert all(fact.organization_id == ORG and fact.tenant_id == TENANT for fact in facts)

    evidence = {fact.evidence_reference for fact in facts}

    assert "file:inventory.csv:row:1" in evidence
    assert "file:cost_export.csv:row:1" in evidence


def test_multi_source_reconciliation_uses_existing_registry(
    tmp_path,
):
    registry = _registry()

    account = _entity(
        registry,
        EntityType.CLOUD_ACCOUNT,
        "111111111111",
        "certified_evidence_package",
        "111111111111",
    )
    resource = _entity(
        registry,
        EntityType.CLOUD_RESOURCE,
        "i-123",
        "certified_evidence_package",
        "i-123",
    )
    application = _entity(
        registry,
        EntityType.APPLICATION,
        "Checkout",
        "certified_evidence_package",
        "Checkout",
    )

    result = execute_certified_package_runtime(
        package_id=PACKAGE,
        sources=_sources(),
        organization_id=ORG,
        tenant_id=TENANT,
        prospect_id=PROSPECT,
        analysis_id=ANALYSIS,
        source_fact_database=tmp_path / "facts.db",
        registry=registry,
    )

    candidate_ids = {
        proposal.candidate_canonical_id
        for proposal in result.reconciliation.proposals
        if proposal.candidate_canonical_id
    }

    assert account.canonical_id in candidate_ids
    assert resource.canonical_id in candidate_ids
    assert application.canonical_id in candidate_ids

    states = {proposal.state.value for proposal in result.reconciliation.proposals}

    assert states


def test_unknown_package_identities_remain_unresolved(
    tmp_path,
):
    registry = _registry()

    _entity(
        registry,
        EntityType.CLOUD_ACCOUNT,
        "111111111111",
        "certified_evidence_package",
        "111111111111",
    )
    _entity(
        registry,
        EntityType.CLOUD_RESOURCE,
        "i-123",
        "certified_evidence_package",
        "i-123",
    )
    _entity(
        registry,
        EntityType.APPLICATION,
        "Checkout",
        "certified_evidence_package",
        "Checkout",
    )

    result = execute_certified_package_runtime(
        package_id=PACKAGE,
        sources=_sources(),
        organization_id=ORG,
        tenant_id=TENANT,
        prospect_id=PROSPECT,
        analysis_id=ANALYSIS,
        source_fact_database=tmp_path / "facts.db",
        registry=registry,
    )

    known_canonical_ids = {entity.canonical_id for entity in registry.list_entities()}

    unknown_observation_ids = {
        "i-inventory-only",
        "i-cost-only",
        "999999999999",
    }

    unsafe_bindings = [
        binding
        for binding in result.reconciliation.bindings
        if (
            binding.source_identifier in unknown_observation_ids
            and binding.canonical_id not in known_canonical_ids
        )
    ]

    assert not unsafe_bindings


def test_replay_does_not_duplicate_current_sourcefacts(
    tmp_path,
):
    registry = _registry()

    _entity(
        registry,
        EntityType.CLOUD_ACCOUNT,
        "111111111111",
        "certified_evidence_package",
        "111111111111",
    )
    _entity(
        registry,
        EntityType.CLOUD_RESOURCE,
        "i-123",
        "certified_evidence_package",
        "i-123",
    )
    _entity(
        registry,
        EntityType.APPLICATION,
        "Checkout",
        "certified_evidence_package",
        "Checkout",
    )

    database = tmp_path / "facts.db"

    first = execute_certified_package_runtime(
        package_id=PACKAGE,
        sources=_sources(),
        organization_id=ORG,
        tenant_id=TENANT,
        prospect_id=PROSPECT,
        analysis_id=ANALYSIS,
        source_fact_database=database,
        registry=registry,
        execution_id="execution-1",
    )

    before = len(first.source_fact_service.repository.list_current_facts(ORG, TENANT))

    second = execute_certified_package_runtime(
        package_id=PACKAGE,
        sources=_sources(),
        organization_id=ORG,
        tenant_id=TENANT,
        prospect_id=PROSPECT,
        analysis_id=ANALYSIS,
        source_fact_database=database,
        registry=registry,
        execution_id="execution-2",
    )

    after = len(second.source_fact_service.repository.list_current_facts(ORG, TENANT))

    assert after == before

    assert sum(item.unchanged_fact_count for item in second.publications) > 0
