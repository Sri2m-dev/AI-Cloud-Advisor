from services.technology_inventory_certification_service import TechnologyInventoryCertificationService


def test_contextless_technology_inventory_is_explicitly_unknown():
    result = TechnologyInventoryCertificationService.get_dashboard()
    assert result["availability"] == "UNKNOWN"
    assert result["dataframes"]["inventory"].empty
