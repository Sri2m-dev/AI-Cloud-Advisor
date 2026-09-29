from pathlib import Path

PAGE = Path("pages/analyze_environment.py")


def _source():
    return PAGE.read_text(encoding="utf-8")


def test_manifest_json_is_supported_as_package_control_document():
    source = _source()

    assert 'type=["csv", "xlsx", "pdf", "json"]' in source
    assert 'name.lower() == "manifest.json"' in source


def test_package_validation_precedes_persistence():
    source = _source()

    validate = source.index("package = validate_evidence_package(bundle)")
    persist = source.index("persist_validated_evidence_package(")

    assert validate < persist


def test_package_uses_declared_cost_source_for_compatibility():
    source = _source()

    assert 'cost_source = package.manifest.source("cost")' in source
    assert "primary_name = cost_source.filename" in source
    assert 'content = package.content("cost")' in source


def test_package_persistence_precedes_governed_admission():
    source = _source()

    persist = source.index("persist_validated_evidence_package(")
    admission = source.index("admission = admit_uploaded_evidence(")

    assert persist < admission


def test_non_package_upload_route_remains_present():
    source = _source()

    assert "if package is not None:" in source
    assert 'if item[0].lower().endswith((".csv", ".xlsx"))' in source
    assert "bundle[0]," in source


def test_arbitrary_json_fails_closed():
    source = _source()

    assert "JSON is accepted only as manifest.json" in source
    assert "Evidence package validation failed:" in source


def test_package_identity_is_stored_in_session():
    source = _source()

    assert 'st.session_state["evidence_package_id"] = package.package_id' in source
    assert 'st.session_state.pop("evidence_package_id", None)' in source


def test_existing_admission_precedes_legacy_ingestion():
    source = _source()

    admission = source.index("admission = admit_uploaded_evidence(")
    legacy = source.index("prospect_analysis = ingest_upload(")

    assert admission < legacy
