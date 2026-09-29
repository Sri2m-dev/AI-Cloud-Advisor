"""Exercise the actual Streamlit upload route and authenticated package pipeline."""

import csv
import hashlib
import io
import json
from dataclasses import replace

import pytest
from cryptography.fernet import Fernet
from streamlit.testing.v1 import AppTest

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.prospect_data_intake_service import create_prospect_tenant
from tests.universal_evidence.test_evidence_package_intelligence import _sources
from universal_evidence.pilot.evidence_package import validate_evidence_package
from universal_evidence.pilot.evidence_package_runtime import analyze_certified_package

ORG = "aaaaaaaa-1111-4111-8111-111111111111"


def package_files():
    files, entries = [], []
    for source in _sources():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(source.rows[0]))
        writer.writeheader()
        writer.writerows(source.rows)
        content = stream.getvalue().encode()
        files.append((source.file_id, content))
        entries.append(
            dict(
                name=source.file_id,
                type=source.source_type,
                sha256=hashlib.sha256(content).hexdigest(),
                bytes=len(content),
            )
        )
    manifest = dict(
        package_version="1.0",
        package_id="generic-closure-test",
        customer="Test",
        engagement="Test",
        files=entries,
        period=dict(start="2025-12-01", end="2026-03-31"),
    )
    return (("manifest.json", json.dumps(manifest).encode()), *files)


def app_session():
    app = AppTest.from_file("pages/analyze_environment.py", default_timeout=180)
    for key, value in dict(
        authenticated=True,
        role="super_admin",
        user="closure@example.invalid",
        email="closure@example.invalid",
        user_email="closure@example.invalid",
        user_id="closure-operator",
        organization_id=ORG,
        organization_name="Closure UAT",
        auth_backend="local",
        authorized_organization_ids=[ORG],
        permissions=[],
        analysis_start_path="upload",
    ).items():
        app.session_state[key] = value
    return app


def upload_files(app, files):
    app.run()
    assert not app.exception
    app.text_input[0].set_value("Closure UAT")
    app.checkbox[0].check()
    app.file_uploader[0].set_value(
        [(n, b, "application/json" if n.endswith(".json") else "text/csv") for n, b in files]
    )
    next(b for b in app.button if b.label == "Continue Analysis").click().run(timeout=180)
    assert not app.exception
    return app


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "false")
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_ROOT", str(tmp_path / "prospects"))
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(tmp_path / "governance.db"))
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_KEY", Fernet.generate_key().decode())
    # STORE_ROOT is imported at application startup; patch the existing storage
    # authority as well as the environment for a test process that imported it.
    import services.prospect_data_intake_service as intake

    monkeypatch.setattr(intake, "STORE_ROOT", tmp_path / "prospects")
    import universal_evidence.pilot.evidence_package_persistence as persistence

    for module in (intake, persistence):
        for value in vars(module).values():
            defaults = getattr(value, "__kwdefaults__", None)
            if defaults and "root" in defaults:
                monkeypatch.setattr(
                    value, "__kwdefaults__", dict(defaults, root=tmp_path / "prospects")
                )
    return tmp_path


def test_application_upload_composes_all_sources_and_renders_provenance(isolated):
    app = upload_files(app_session(), package_files())
    assert not app.error, [e.value for e in app.error]
    result = app.session_state["evidence_package_result"]
    assert len(result.sources) == 4
    assert result.intelligence.governed_cost == 19.75
    assert all(s.mapping_decision_ids and s.normalization_references for s in result.sources)
    assert len({a.scope.key for a in result.admissions}) == 1
    assert len(app.dataframe) == 4
    assert any("generic-closure-test" in str(m.value) for m in app.markdown)
    assert any("UNKNOWN" in c.value for c in app.caption)
    assert not app.file_uploader
    app.run()
    assert not app.exception
    assert app.session_state["evidence_package_result"] is result


@pytest.mark.parametrize("changed", ["user_id", "organization_id", "prospect_tenant"])
def test_package_results_reject_replayed_session_scope(isolated, changed):
    app = upload_files(app_session(), package_files())
    assert not app.error, [e.value for e in app.error]
    if changed == "prospect_tenant":
        app.session_state[changed] = replace(app.session_state[changed], tenant_id="other-prospect")
    elif changed == "organization_id":
        other = "bbbbbbbb-1111-4111-8111-111111111111"
        app.session_state[changed] = other
        app.session_state["authorized_organization_ids"] = [other]
    else:
        app.session_state[changed] = "other-owner"
    from shared.evidence_context import resolve_active_evidence_context

    assert not resolve_active_evidence_context(app.session_state.filtered_state).is_prospect
    app.run()
    assert not app.exception
    assert any("unavailable in this workspace" in e.value for e in app.error)
    assert not app.dataframe


def test_package_failure_does_not_fall_back_to_cost_only(isolated, monkeypatch):
    import universal_evidence.pilot.evidence_package_runtime as runtime

    def blocked(**kwargs):
        raise PermissionError("governance blocked")

    monkeypatch.setattr(runtime, "analyze_certified_package", blocked)
    app = upload_files(app_session(), package_files())
    assert any("Certified package analysis failed" in e.value for e in app.error)
    assert "evidence_package_result" not in app.session_state
    assert "prospect_analysis" not in app.session_state


def test_sourcefacts_are_isolated_between_prospects(isolated):
    key = Fernet.generate_key()
    ctx = AuthenticatedTenantContext(
        ORG, "Test", "operator", "operator@example.invalid", "super_admin", frozenset(), ORG
    )
    results = []
    for name in ("First", "Second"):
        tenant = create_prospect_tenant(
            name,
            consent=True,
            actor=ctx.user_id,
            role=ctx.role,
            root=isolated / "prospects",
            key=key,
        )
        results.append(
            analyze_certified_package(
                package=validate_evidence_package(package_files()),
                prospect_tenant=tenant,
                authenticated=ctx,
                source_fact_root=isolated / "facts",
            )
        )
    assert (
        results[0].runtime.source_fact_service.repository.database
        != results[1].runtime.source_fact_service.repository.database
    )
    assert results[0].admissions[0].scope.analysis_id != results[1].admissions[0].scope.analysis_id
    assert not results[0].runtime.source_fact_service.repository.list_current_facts(
        "other", "other"
    )


def test_legacy_single_file_csv_upload_still_works(isolated, monkeypatch):
    import streamlit as st

    # AppTest runs one page without the application navigation registry.
    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)
    content = b"UsageAccountId,ProductCode,UnblendedCost,Currency\n111,AmazonEC2,12.50,USD\n"
    app = upload_files(app_session(), (("legacy.csv", content),))
    assert not app.error, [e.value for e in app.error]
    assert "evidence_package_result" not in app.session_state
    assert app.session_state["prospect_analysis"].total_spend == 12.5
    assert app.session_state["pue_upload_admission"].original_filename == "legacy.csv"


def test_package_context_clears_with_prospect_workspace(isolated):
    from shared.evidence_context import clear_prospect_context, resolve_active_evidence_context

    app = upload_files(app_session(), package_files())
    session = app.session_state.filtered_state
    assert resolve_active_evidence_context(session).is_prospect
    clear_prospect_context(session)
    assert "evidence_package_result" not in session
    assert "evidence_package_id" not in session
