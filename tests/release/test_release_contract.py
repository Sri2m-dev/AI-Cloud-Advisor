from pathlib import Path

from backend.main import app
from nexora_release import RELEASE_NAME, RELEASE_PHASE, RELEASE_VERSION


def test_product_version_has_one_authoritative_runtime_source():
    assert RELEASE_VERSION == "2.0.0"
    assert RELEASE_NAME == "Nexora 2.0"
    assert RELEASE_PHASE == "REL-001"
    assert app.version == RELEASE_VERSION


def test_release_documentation_and_runtime_contract_exist():
    required = (
        "README.md",
        ".env.example",
        "docs/release/REL_001_RELEASE_CANDIDATE.md",
        "docs/release/PRODUCTION_CONFIGURATION.md",
        "docs/release/KNOWN_LIMITATIONS.md",
    )
    assert all(Path(item).is_file() for item in required)
