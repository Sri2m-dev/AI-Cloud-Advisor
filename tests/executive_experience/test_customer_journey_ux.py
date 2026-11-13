import json
from pathlib import Path

from auth.connector_context import CONNECTOR_ADMIN_ROLES
from components.navigation.sidebar import (
    build_persona_navigation_items,
    filter_navigation_by_v1_scope,
)
from components.sidebar_navigation import DEFAULT_ROLE_PAGE, PAGE_PATHS, get_role_pages
from services.local_auth_service import LOCAL_PERSONAS

ROOT = Path(__file__).parents[2]


def test_customer_workspace_is_navigable_for_customer_and_approval_roles():
    roles = ("client_admin", "executive", "cio", "finance", "auditor", "operations")
    for role in roles:
        items = build_persona_navigation_items(role=role, page_paths=PAGE_PATHS)
        assert any(
            child["label"] == "Home"
            and child["page"] == PAGE_PATHS["Customer Workspace"]
            for section in items
            for child in section["children"]
        )
        visible = filter_navigation_by_v1_scope(
            items,
            role,
            page_paths=PAGE_PATHS,
            role_pages={role: get_role_pages(role)},
        )
        visible_pages = {
            child["page"]
            for section in visible
            for child in section["children"]
        }
        assert visible_pages
        assert visible_pages <= {
            PAGE_PATHS["Customer Workspace"],
            PAGE_PATHS["Approvals"],
            PAGE_PATHS["Reports"],
        }


def test_canonical_persona_start_surfaces_are_explicit():
    assert PAGE_PATHS["Welcome"] == "pages/welcome.py"
    assert DEFAULT_ROLE_PAGE["executive"] == "pages/ceo_workspace.py"
    assert DEFAULT_ROLE_PAGE["sales_engineer"] == "pages/welcome.py"
    assert get_role_pages("executive")[0] == "Welcome"
    assert get_role_pages("sales_engineer")[:2] == ["Welcome", "Analyse Your Environment"]


def test_sales_engineer_persona_and_connector_boundary_are_explicit():
    personas = {(email, role) for email, role, _password in LOCAL_PERSONAS}
    assert ("sales.engineer@company.com", "sales_engineer") in personas
    assert CONNECTOR_ADMIN_ROLES == {"client_admin", "sales_engineer", "super_admin"}


def test_analysis_journey_uses_certified_paths_and_truthful_gcp_limit():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "pages/prospect_data_intake.py" in source
    assert "AWSConnectorService.test_connection" in source
    assert "AWSConnectorService.sync_all" in source
    assert "AzureConnectorService.test_connection" in source
    assert "AzureConnectorService.discover_to_data_fabric" in source
    assert "Live connection is not yet certified" in source
    assert "Nexora does not simulate progress" in source


def test_analysis_starts_with_four_real_governed_actions():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "How would you like to start?" in source
    assert all(
        label in source
        for label in (
            "Configure AWS →",
            "Configure Azure →",
            "Choose files →",
            "Launch Sample Enterprise →",
        )
    )
    assert '"pages/prospect_data_intake.py"' in source
    assert "demo_mode_enabled() and is_demo_tenant(organization_id)" in source
    assert "Learn more about supported evidence and secure processing" in source


def test_analysis_defers_rbac_until_execution_without_simulating_connections():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "disabled=not connector_admin" not in source
    assert "disabled=not upload_operator" not in source
    assert "Completing a live connection requires" in source
    assert "Uploading production or prospect data requires" in source
    assert "No cloud credentials" in source and "collected or stored" in source
    assert "No file has been selected" in source and "uploaded" in source
    assert "Continue with Sample Enterprise" in source
    assert "mock connection" not in source.lower()


def test_analysis_executes_existing_connector_and_intake_services_inline():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "st.file_uploader" in source
    assert "create_prospect_tenant" in source
    assert "ingest_upload" in source
    assert "prospect_encryption_key" in source
    assert "AWSConnectorService.save_config" in source
    assert "AzureConnectorService.save_config" in source
    assert "tenant_context = authenticated_tenant_context(st.session_state)" in source
    assert "tenant_context.organization_id" in source
    assert '("Malware scan", "Passed")' in source
    assert '("Schema", "Validated")' in source
    assert "Business services completed" not in source


def test_analysis_is_a_focused_four_step_wizard():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "if not selected_path:" in source
    assert "actions = st.columns(len(action_specs)) if action_specs else []" in source
    assert "for column, card in zip(actions, action_specs, strict=True):" in source
    assert "if not selected_path\n    else ()" in source
    assert '"← Choose another source"' in source
    assert all(f'"STEP {step} OF 4"' not in source for step in range(1, 5))
    assert 'st.caption(f"STEP {step} OF 4")' in source
    assert '"Connect {provider}"' in source
    assert '"Analyze environment"' in source
    assert '"Prospect brief ready"' in source


def test_analysis_exposes_only_certified_live_onboarding_capabilities():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "IAM Role (Certified)" in source
    assert "Nexora Runtime Identity" in source
    assert "Client secrets are never stored" in source
    assert "credential reference is resolved from the Nexora runtime configuration" in source
    assert "Managed Identity and management-group onboarding are not yet certified" in source
    assert "Certified packages require manifest.json" in source
    assert "standalone ZIP is not supported" in source
    assert "Start Discovery" in source
    assert "Continue Analysis" in source


def test_azure_start_discovery_uses_authenticated_canonical_path_only():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert 'tenant_context = authenticated_tenant_context(st.session_state)' in source
    assert 'disabled=not azure_runtime' in source
    assert 'AzureConnectorService.discover_to_data_fabric(' in source
    assert 'enabled=False' in source
    assert 'AzureConnectorService.sync_all' not in source


def test_analysis_completion_uses_returned_evidence_not_synthetic_progress():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "_render_cloud_results(cloud_result)" in source
    cloud_result_rendering = source.rsplit(
        'cloud_result = st.session_state.get("environment_analysis_result")', 1
    )[1].split('prospect_result = st.session_state.get("prospect_analysis")', 1)[0]
    assert "AWS discovery completed; persistence blocked" in cloud_result_rendering
    assert "Azure resource discovery complete" in cloud_result_rendering
    assert "Financial cost ingestion: NOT PERFORMED" in cloud_result_rendering
    assert "Dashboard financial readiness: UNKNOWN" in cloud_result_rendering
    assert "Executive brief ready" not in cloud_result_rendering
    assert "retrieved" in source
    assert "prospect_result.total_spend" in source
    assert "prospect_result.evidence_coverage" in source
    assert "prospect_result.opportunity_evidence_qualified" in source
    assert "opportunity_realized" not in source


def test_analysis_demo_card_matches_the_governed_synthetic_dataset():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    payload = json.loads(
        (ROOT / "data" / "demo" / "nexora_global_retail.json").read_text(encoding="utf-8")
    )
    estate = payload["metrics"]
    assert f"{estate['business_services']:,} business services" in source
    assert f"{estate['applications']:,} applications" in source
    assert f"{estate['cloud_accounts']:,} cloud accounts" in source
    assert f"${estate['annual_technology_spend'] / 1_000_000:.0f}M governed spend" in source


def test_executive_actions_and_chart_conclusions_are_business_first():
    decisions = (ROOT / "pages" / "decision_intelligence.py").read_text(encoding="utf-8")
    experience = (ROOT / "components" / "executive_experience.py").read_text(encoding="utf-8")
    assert all(label in decisions for label in ("View Impact", "Trace Evidence", "Review Approval"))
    assert experience.count("**What this means:**") >= 6
    assert "TODAY'S EXECUTIVE BRIEF" in experience
    assert "Confidence, evidence, and delay consequence" in experience
    assert "FINANCIAL POSITION" in experience
    assert "zip(cols, snapshot.metrics, strict=True)" not in experience


def test_ask_nexora_keeps_technical_context_behind_advanced_evidence():
    source = (ROOT / "pages" / "ai_copilot.py").read_text(encoding="utf-8")
    assert "Turn evidence into an executive answer" in source
    assert "Advanced evidence and source traceability" in source
    assert "Context Panel" not in source


def test_progressive_disclosure_and_accessible_motion_are_present():
    services = (ROOT / "pages" / "business_services.py").read_text(encoding="utf-8")
    styles = (ROOT / "shared" / "styles.py").read_text(encoding="utf-8")
    assert "Show detailed certification evidence" in services
    assert "Dependency and Digital Twin path" in services
    assert "prefers-reduced-motion" in styles
    assert ":focus-visible" in styles


def test_v22_premium_shell_and_onboarding_are_presentation_only():
    styles = (ROOT / "shared" / "styles.py").read_text(encoding="utf-8")
    welcome = (ROOT / "pages" / "welcome.py").read_text(encoding="utf-8")
    analysis = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    intake = (ROOT / "pages" / "prospect_data_intake.py").read_text(encoding="utf-8")
    assert "nexora-product-bar" in styles
    assert "Enterprise Decision Intelligence" in styles
    assert "Good morning" in welcome
    assert "Coming Soon" in analysis
    assert "Live connection is not yet certified" in analysis
    assert "PDF invoices are not yet supported" in intake


def test_v22_digital_twin_uses_existing_relationship_path():
    twin = (ROOT / "pages" / "twin_explorer.py").read_text(encoding="utf-8")
    assert "nexora-twin-path" in twin
    assert 'journey.get("twin_path")' in twin
    assert "new graph" not in twin.lower()


def test_v30_home_composes_existing_certified_story_and_actions():
    source = (ROOT / "pages" / "welcome.py").read_text(encoding="utf-8")
    assert "TODAY'S ENTERPRISE POSTURE" in source
    assert "Three decisions requiring leadership attention" in source
    assert "Executive AI summary" in source
    assert "Enterprise Digital Twin" in source
    assert "Prepare Board Pack" in source
    assert "load_demo_tenant" in source
    assert "nexora-posture-strip" in source
    assert "Not realized value" in source


def test_v30_polish_uses_governed_demo_answers_and_domain_visual_language():
    copilot = (ROOT / "pages" / "enterprise_ai_copilot.py").read_text(encoding="utf-8")
    demo_ask = (ROOT / "services" / "demo_ask_nexora_service.py").read_text(
        encoding="utf-8"
    )
    styles = (ROOT / "shared" / "styles.py").read_text(encoding="utf-8")
    navigation = (ROOT / "components" / "navigation" / "sidebar.py").read_text(encoding="utf-8")
    assert "DemoAskNexoraService" in copilot
    assert "qualified opportunity" in demo_ask
    assert "verified as realized value" in demo_ask
    assert "nexora-domain-card.finance" in styles
    assert "nexora-domain-card.risk" in styles
    assert '"section": "Business"' in navigation
    assert '"section": "Governance"' in navigation


def test_v30_progressive_disclosure_hides_technical_surfaces_by_default():
    services = (ROOT / "pages" / "business_services.py").read_text(encoding="utf-8")
    copilot = (ROOT / "pages" / "enterprise_ai_copilot.py").read_text(encoding="utf-8")
    assert "Show operational mappings and certification detail" in services
    assert "Technical mappings and evidence are intentionally hidden" in services
    assert 'st.expander("Show Evidence")' in copilot
    assert "I cannot certify an answer" in copilot


def test_v1_reports_are_customer_workflow_export_alias():
    source = (ROOT / "pages" / "reports.py").read_text(encoding="utf-8")
    assert "require_role(_CUSTOMER_ROLES)" in source
    assert "Evidence-linked Exports" in source
    assert "only after the Finance, CIO, " in source
    assert 'v1_page_link(\n    "pages/customer_workspace.py"' in source

def test_production_ga_executive_metric_grid_is_bounded():
    experience = Path(
        "components/executive_experience.py"
    ).read_text(encoding="utf-8")

    assert "range(0, len(snapshot.metrics), 4)" in experience
    assert (
        "metric_row = snapshot.metrics[metric_index : metric_index + 4]"
        in experience
    )
    assert "executive_columns(len(metric_row))" in experience
    assert "for column, metric in zip(cols, metric_row):" in experience
    assert "executive_columns(len(snapshot.metrics))" not in experience
