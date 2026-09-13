from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
LEGACY_NAMES = (
    "application_registry",
    "application_spend_mapping",
    "approval_requests",
    "approval_history",
    "mart_application_spend",
    "mart_enterprise_spend",
    "mart_enterprise_spend_v2",
    "technology_inventory",
)
RUNTIME_ROOTS = ("services", "repositories", "pages", "backend", "connectors", "enterprise_copilot", "shared")


def test_rc001_reachable_manifest_excludes_completed_legacy_paths():
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for root in RUNTIME_ROOTS
        for path in (ROOT / root).rglob("*.py")
    )
    assert not re.search(r'\.table\(["\']mart_enterprise_spend_v2["\']\)', text)
    assert "application_spend_mapping" not in (ROOT / "services/asset_mapping_remediation_service.py").read_text()
    technology_service = (ROOT / "services/technology_inventory_certification_service.py").read_text()
    assert not re.search(r'\.table\(["\']technology_inventory["\']\)', technology_service)


def test_rc001_legacy_names_are_explicitly_tracked():
    contract = (ROOT / "docs/cmp/CMP-P6-SC-002/REPORT.md").read_text(encoding="utf-8")
    for name in LEGACY_NAMES:
        assert name in contract
