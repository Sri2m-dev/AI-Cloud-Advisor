from connector_adapters.azure_source_fact_mapper import AzureSourceFactMapper

SUBSCRIPTION = "11111111-2222-4333-8444-555555555555"


def resource(resource_type, resource_id, name):
    return {
        "provider": "Azure",
        "subscription_id": SUBSCRIPTION,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "name": name,
        "region": "eastus",
        "resource_group": "rg-test",
        "status": "ACTIVE",
    }


def test_maps_subscription_and_only_supported_live_resource_types():
    mapper = AzureSourceFactMapper()
    resource_group_id = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-test"
    resources = (
        resource("Azure Resource Group", resource_group_id, "rg-test"),
        resource(
            "Azure VM",
            f"{resource_group_id}/providers/Microsoft.Compute/virtualMachines/vm-test",
            "vm-test",
        ),
        resource(
            "Azure Storage Account",
            f"{resource_group_id}/providers/Microsoft.Storage/storageAccounts/sttest",
            "sttest",
        ),
        resource(
            "Azure VNet",
            f"{resource_group_id}/providers/Microsoft.Network/virtualNetworks/vnet-test",
            "vnet-test",
        ),
        resource("Azure SQL Database", "unsupported-id", "not-projected"),
    )
    mapped = mapper.map_resources(
        ({"cloud": "azure", "account_id": SUBSCRIPTION, "account_name": "azure-test"},),
        resources,
    )

    assert len(mapped) == 5
    by_type = {item.source_fact.value["resource_type"]: item for item in mapped}
    assert set(by_type) == {
        "Azure Subscription", "Azure Resource Group", "Azure VM",
        "Azure Storage Account", "Azure VNet",
    }
    for item in mapped:
        fact = item.source_fact
        assert fact.source_record_id == fact.value["resource_id"]
        assert fact.subject_reference == fact.value["resource_id"]
        assert fact.value["provider"] == "Azure"
        assert fact.value["subscription_id"] == SUBSCRIPTION
        assert fact.provenance["resource_id"] == fact.source_record_id
        assert item.projection_rule_id in mapper.projection_rules()


def test_unknown_resource_type_and_provider_are_not_mapped():
    mapper = AzureSourceFactMapper()
    mapped = mapper.map_resources(
        (),
        (
            resource("Azure SQL Database", "id-sql", "sql"),
            {**resource("Azure VM", "id-other", "other"), "provider": "Other"},
        ),
    )

    assert mapped == ()
    assert mapper.map_relationships((resource("Azure VM", "vm", "vm"),)) == ()
