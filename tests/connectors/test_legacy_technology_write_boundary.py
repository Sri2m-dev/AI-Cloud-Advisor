from connectors.common.persistence import upsert_technology_inventory


def test_legacy_technology_inventory_write_is_explicitly_unsupported():
    assert upsert_technology_inventory([{"technology_name": "observed"}], "org-1") is False
