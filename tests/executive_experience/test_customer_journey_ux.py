import json
from pathlib import Path

from auth.connector_context import CONNECTOR_ADMIN_ROLES
from components.sidebar_navigation import DEFAULT_ROLE_PAGE, PAGE_PATHS, get_role_pages
from services.local_auth_service import LOCAL_PERSONAS

ROOT = Path(__file__).parents[2]


def test_welcome_is_the_executive_and_sales_engineer_start_surface():
    assert PAGE_PATHS["Welcome"] == "pages/welcome.py"
    assert DEFAULT_ROLE_PAGE["executive"] == "pages/welcome.py"
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
    assert "AzureConnectorService.sync_all" in source
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
    assert 'st.switch_page("pages/welcome.py")' in source
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
    assert source.count("organization_id=get_current_organization_id()") >= 4
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
    assert '"Executive brief ready"' in source
    assert '"Prospect brief ready"' in source


def test_analysis_exposes_only_certified_live_onboarding_capabilities():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "IAM Role (Certified)" in source
    assert "Service Principal (Certified)" in source
    assert "Access Key and organization-wide authentication are not yet certified" in source
    assert "Managed Identity and management-group onboarding are not yet certified" in source
    assert "JSON and standalone ZIP are not yet supported" in source
    assert "Start Discovery" in source
    assert "Continue Analysis" in source


def test_analysis_completion_uses_returned_evidence_not_synthetic_progress():
    source = (ROOT / "pages" / "analyze_environment.py").read_text(encoding="utf-8")
    assert "_render_cloud_results(cloud_result)" in source
    assert '("Technology inventory", "Persisted")' in source
    assert '("Relationship graph", "Persisted")' in source
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
    styles = (ROOT / "shared" / "styles.py").read_text(encoding="utf-8")
    navigation = (ROOT / "components" / "navigation" / "sidebar.py").read_text(encoding="utf-8")
    assert "_demo_executive_answer" in copilot
    assert "qualified opportunity" in copilot
    assert "verified as realized value" in copilot
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


def test_v30_reports_only_preview_existing_generated_outputs():
    source = (ROOT / "pages" / "reports.py").read_text(encoding="utf-8")
    assert "generated_report_thumbnail" in source
    assert 'str(row.get("status", "")).lower() != "generated"' in source
    assert 'Path(str(row.get("file_name") or "")).name' in source
    assert "Generated report · first-page preview" in source
