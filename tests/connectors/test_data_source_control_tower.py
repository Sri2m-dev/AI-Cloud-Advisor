"""Focused test suite for WS4: Data Source Control Tower."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from connector_adapters.live_cost import AWSLiveCostConnector
from connector_registry.live_sources import LiveSourceRepository
from services.data_source_control_tower_service import (
    DataSourceControlTowerService,
    FreshnessStatus,
    SourceHealth,
)
from services.live_source_service import LiveSourceService


@pytest.fixture
def mock_fernet(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", "sJ_hQ1s36WlH-vG4eZgP8jKxTmNxqW9d0FzV1s2A3b4=")


@pytest.fixture
def tenant_a():
    org_id = str(uuid.uuid4())
    return AuthenticatedTenantContext(
        organization_id=org_id,
        organization_name="Control Tower Org",
        user_id="admin@tower.com",
        user_email="admin@tower.com",
        role="client_admin",
        authorization_claims=frozenset(["admin"]),
        tenant_id=org_id,
    )


@pytest.fixture
def tenant_b():
    org_id = str(uuid.uuid4())
    return AuthenticatedTenantContext(
        organization_id=org_id,
        organization_name="Other Org",
        user_id="admin@other.com",
        user_email="admin@other.com",
        role="client_admin",
        authorization_claims=frozenset(["admin"]),
        tenant_id=org_id,
    )


@pytest.fixture
def control_tower_setup(tmp_path, mock_fernet):
    db_path = tmp_path / "tower_test.db"
    repo = LiveSourceRepository(db_path)
    live_service = LiveSourceService(repo)
    tower_service = DataSourceControlTowerService(live_service)
    return tower_service, live_service, repo


# ============================================================
# 1. Unified Inventory Visibility (AWS, Azure, M365)
# ============================================================


def test_unified_source_inventory_visibility(control_tower_setup, tenant_a):
    tower, live, _ = control_tower_setup

    # 1. Create AWS source
    live.create(
        tenant_a,
        provider="aws",
        display_name="Production AWS Core",
        configuration={
            "account_id": "111222333444",
            "role_arn": "arn:aws:iam::111222333444:role/NexoraRole",
            "region": "us-east-1",
        },
        secrets={},
    )

    # 2. Create Azure source
    live.create(
        tenant_a,
        provider="azure",
        display_name="Production Azure Cloud",
        configuration={
            "tenant_id": str(uuid.uuid4()),
            "subscription_id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
        },
        secrets={"client_secret": "az-secret"},
    )

    # 3. Create M365 source
    live.create(
        tenant_a,
        provider="m365",
        display_name="Corporate M365 SaaS",
        configuration={
            "tenant_id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
        },
        secrets={"client_secret": "m365-secret"},
    )

    sources = tower.list_unified_sources(tenant_a)
    assert len(sources) == 3

    providers = {s.provider for s in sources}
    assert providers == {"aws", "azure", "m365"}

    for s in sources:
        assert s.health == SourceHealth.NEVER_SYNCED
        assert s.freshness == FreshnessStatus.UNKNOWN
        assert s.active is False
        assert s.provenance_reference == f"source-instance:{s.source_id}"


# ============================================================
# 2. Health and Freshness State Progression
# ============================================================


def test_source_health_and_freshness_evaluation(control_tower_setup, tenant_a):
    tower, live, _ = control_tower_setup

    mock_conn = MagicMock()
    mock_conn.authenticate.return_value = True
    mock_conn.extract.return_value = [
        {
            "start": "2026-09-01",
            "end": "2026-09-02",
            "service": "Compute",
            "amount": "100.00",
            "currency": "USD",
        }
    ]
    mock_conn.normalize.return_value = ()
    mock_conn.validate.return_value = (True, ())

    real_aws = AWSLiveCostConnector(
        {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        MagicMock(),
    )
    mock_conn.normalize = real_aws.normalize
    mock_conn.validate = real_aws.validate

    live.factories = {"aws": lambda c, cred, now: mock_conn}

    src = live.create(
        tenant_a,
        provider="aws",
        display_name="Healthy AWS",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )
    live.validate_connection(tenant_a, src["source_id"])
    live.set_active(tenant_a, src["source_id"], True)

    # Health before sync: NEVER_SYNCED
    detail = tower.get_source_detail(tenant_a, src["source_id"])
    assert detail.health == SourceHealth.NEVER_SYNCED

    # Sync successfully
    live.sync(tenant_a, src["source_id"], request_key="sync-health-1")
    live.set_schedule(tenant_a, src["source_id"], enabled=True, cadence_seconds=86400)

    # Health after success: HEALTHY & FRESH
    detail = tower.get_source_detail(tenant_a, src["source_id"])
    assert detail.health == SourceHealth.HEALTHY
    assert detail.freshness == FreshnessStatus.FRESH
    assert detail.last_sync_status == "SUCCEEDED"

    # Fast-forward past the daily cadence and bounded one-hour grace.
    tower.clock = lambda: datetime.now(timezone.utc) + timedelta(days=2)
    detail_stale = tower.get_source_detail(tenant_a, src["source_id"])
    assert detail_stale.freshness == FreshnessStatus.STALE
    assert detail_stale.health == SourceHealth.STALE


# ============================================================
# 3. Operational Actions: Sync, Enable/Disable, History
# ============================================================


def test_control_tower_operational_lifecycle(control_tower_setup, tenant_a):
    tower, live, _ = control_tower_setup

    mock_conn = MagicMock()
    mock_conn.authenticate.return_value = True
    mock_conn.extract.return_value = []
    mock_conn.normalize.return_value = ()
    mock_conn.validate.return_value = (True, ())
    live.factories = {"aws": lambda c, cred, now: mock_conn}

    src = live.create(
        tenant_a,
        provider="aws",
        display_name="Lifecycle AWS",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )
    live.validate_connection(tenant_a, src["source_id"])
    tower.toggle_source_active(tenant_a, src["source_id"], True)

    detail = tower.get_source_detail(tenant_a, src["source_id"])
    assert detail.active is True

    # Manual sync through control tower service
    res = tower.trigger_manual_sync(tenant_a, src["source_id"], request_key="tower-manual-1")
    assert res["status"] == "SUCCEEDED"

    # Check execution history
    history = tower.get_execution_history(tenant_a, src["source_id"])
    assert len(history) == 1
    assert history[0].status == "SUCCEEDED"
    assert history[0].trigger_type == "manual"

    # Disable source
    tower.toggle_source_active(tenant_a, src["source_id"], False)
    detail_dis = tower.get_source_detail(tenant_a, src["source_id"])
    assert detail_dis.active is False
    assert detail_dis.health == SourceHealth.DISABLED


# ============================================================
# 4. Tenant Isolation
# ============================================================


def test_control_tower_tenant_isolation(control_tower_setup, tenant_a, tenant_b):
    tower, live, _ = control_tower_setup

    src = live.create(
        tenant_a,
        provider="aws",
        display_name="Tenant A Isolated AWS",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )

    # Tenant B cannot list or get details
    sources_b = tower.list_unified_sources(tenant_b)
    assert len(sources_b) == 0

    assert tower.get_source_detail(tenant_b, src["source_id"]) is None

    with pytest.raises(PermissionError):
        tower.get_execution_history(tenant_b, src["source_id"])

    with pytest.raises(PermissionError):
        tower.trigger_manual_sync(tenant_b, src["source_id"], "key-x")

    with pytest.raises(PermissionError):
        tower.toggle_source_active(tenant_b, src["source_id"], True)


@pytest.fixture
def active_source(control_tower_setup, tenant_a):
    tower, live, repo = control_tower_setup
    connector = MagicMock()
    connector.authenticate.return_value = True
    connector.extract.return_value = []
    connector.normalize.return_value = ()
    connector.validate.return_value = (True, ())
    live.factories = {"aws": lambda c, cred, now: connector}
    src = live.create(
        tenant_a,
        provider="aws",
        display_name="Synthetic AWS",
        configuration={
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Role",
            "region": "us-east-1",
        },
        secrets={},
    )
    live.validate_connection(tenant_a, src["source_id"])
    live.set_active(tenant_a, src["source_id"], True)
    return src["source_id"], connector


@pytest.mark.parametrize(
    "role,mutation",
    [
        ("client_admin", True),
        ("super_admin", True),
        ("technical", False),
        ("operations", False),
        ("viewer", False),
        ("executive", False),
        ("cio", False),
    ],
)
def test_role_matrix(control_tower_setup, tenant_a, active_source, role, mutation):
    from dataclasses import replace

    tower, live, _ = control_tower_setup
    source_id, connector = active_source
    context = replace(tenant_a, role=role)
    assert tower.get_source_detail(context, source_id) is not None
    before = connector.authenticate.call_count
    if mutation:
        assert tower.trigger_manual_sync(context, source_id, "role-test")["status"] == "SUCCEEDED"
        tower.toggle_source_active(context, source_id, False)
        live.validate_connection(context, source_id)
        tower.toggle_source_active(context, source_id, True)
    else:
        with pytest.raises(PermissionError):
            tower.trigger_manual_sync(context, source_id, "role-test")
        for enabled in (True, False):
            with pytest.raises(PermissionError):
                tower.toggle_source_active(context, source_id, enabled)
        assert connector.authenticate.call_count == before
        assert tower.get_execution_history(context, source_id) == ()
        assert tower.get_source_detail(context, source_id).active


@pytest.mark.parametrize(
    "status,active,latest,freshness,expected",
    [
        ("DISABLED", False, "FAILED", FreshnessStatus.STALE, SourceHealth.DISABLED),
        ("ACTIVE", True, "NEVER_SYNCED", FreshnessStatus.UNKNOWN, SourceHealth.NEVER_SYNCED),
        ("ACTIVE", True, "SUCCEEDED", FreshnessStatus.STALE, SourceHealth.STALE),
        ("ACTIVE", True, "FAILED", FreshnessStatus.FRESH, SourceHealth.FAILED),
        ("ACTIVE", True, "SUCCEEDED", FreshnessStatus.UNKNOWN, SourceHealth.UNKNOWN),
        ("ACTIVE", True, "UNKNOWN", FreshnessStatus.UNKNOWN, SourceHealth.UNKNOWN),
        ("ACTIVE", True, "RUNNING", FreshnessStatus.FRESH, SourceHealth.DEGRADED),
        ("ACTIVE", True, "SUCCEEDED", FreshnessStatus.FRESH, SourceHealth.HEALTHY),
    ],
)
def test_no_false_healthy(status, active, latest, freshness, expected):
    assert (
        DataSourceControlTowerService()._evaluate_health(status, active, latest, freshness)
        == expected
    )


@pytest.mark.parametrize(
    "enabled,cadence,success,next_run,expected",
    [
        (False, 86400, "2026-09-13T11:59:00+00:00", None, FreshnessStatus.UNKNOWN),
        (True, 0, "2026-09-13T11:59:00+00:00", None, FreshnessStatus.UNKNOWN),
        (True, 86400, None, None, FreshnessStatus.UNKNOWN),
        (True, 86400, "invalid", None, FreshnessStatus.UNKNOWN),
        (True, 86400, "2026-09-13T11:59:00", None, FreshnessStatus.UNKNOWN),
        (True, 86400, "2026-09-14T00:00:00+00:00", None, FreshnessStatus.UNKNOWN),
        (True, 86400, "2026-09-12T11:00:00+00:00", None, FreshnessStatus.FRESH),
        (True, 86400, "2026-09-12T10:59:59+00:00", None, FreshnessStatus.STALE),
        (
            True,
            86400,
            "2026-09-13T09:00:00+00:00",
            "2026-09-13T10:00:00+00:00",
            FreshnessStatus.STALE,
        ),
    ],
)
def test_freshness_requires_schedule_evidence(enabled, cadence, success, next_run, expected):
    tower = DataSourceControlTowerService(
        clock=lambda: datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    )
    assert tower._evaluate_freshness(success, enabled, cadence, "cloud_api", next_run) == expected


def test_recent_failure_not_hidden_and_errors_safe(control_tower_setup, tenant_a, active_source):
    tower, live, _ = control_tower_setup
    source_id, connector = active_source
    live.set_schedule(tenant_a, source_id, enabled=True, cadence_seconds=3600)
    first = tower.trigger_manual_sync(tenant_a, source_id, "first")
    success_at = tower.get_source_detail(tenant_a, source_id).last_success_at
    connector.authenticate.side_effect = RuntimeError("Bearer synthetic-secret-must-not-render")
    second = tower.trigger_manual_sync(tenant_a, source_id, "second")
    detail = tower.get_source_detail(tenant_a, source_id)
    history = tower.get_execution_history(tenant_a, source_id)
    assert first["status"] == "SUCCEEDED" and second["status"] == "FAILED"
    assert detail.health == SourceHealth.FAILED
    assert detail.last_success_at == success_at
    assert detail.last_sync_status == "FAILED"
    assert detail.last_sync_at == second["completed_at"]
    assert history[0].execution_id == second["execution_id"]
    assert detail.records_ingested == second["records_ingested"]
    assert "synthetic-secret" not in repr(detail) + repr(history)
    assert "credential_ciphertext" not in repr(detail)
    assert detail.safe_error_summary
    tower.toggle_source_active(tenant_a, source_id, False)
    with pytest.raises(ValueError, match="DISABLED"):
        tower.trigger_manual_sync(tenant_a, source_id, "disabled")
    assert tower.get_source_detail(tenant_a, source_id).health == SourceHealth.DISABLED


def test_manual_sync_idempotency_and_concurrency(control_tower_setup, tenant_a, active_source):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    tower, _, _ = control_tower_setup
    source_id, connector = active_source
    entered, release = Event(), Event()

    def hold():
        entered.set()
        assert release.wait(10)
        return []

    connector.extract.side_effect = hold
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(tower.trigger_manual_sync, tenant_a, source_id, "one")
        try:
            assert entered.wait(10)
            duplicate = tower.trigger_manual_sync(tenant_a, source_id, "one")
            assert duplicate["status"] == "RUNNING"
            with pytest.raises(ValueError, match="BUSY"):
                tower.trigger_manual_sync(tenant_a, source_id, "two")
        finally:
            release.set()
        result = pending.result(timeout=10)
    assert result["status"] == "SUCCEEDED"
    assert tower.trigger_manual_sync(tenant_a, source_id, "one") == result
    assert len(tower.get_execution_history(tenant_a, source_id)) == 1


@pytest.mark.parametrize("role", ["client_admin", "viewer", "technical", "operations", "executive"])
def test_streamlit_page_actions_and_safe_render(
    control_tower_setup, tenant_a, active_source, monkeypatch, role
):
    from dataclasses import replace

    from streamlit.testing.v1 import AppTest

    import components.sidebar_navigation
    import services.live_source_service

    tower, live, _ = control_tower_setup
    source_id, _ = active_source
    tower.trigger_manual_sync(tenant_a, source_id, "ui-seed")
    live.create(
        tenant_a,
        provider="azure",
        display_name="Synthetic Azure",
        configuration={
            "tenant_id": str(uuid.uuid4()),
            "subscription_id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
        },
        secrets={"client_secret": "ui-secret"},
    )
    live.create(
        tenant_a,
        provider="m365",
        display_name="Synthetic M365",
        configuration={"tenant_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4())},
        secrets={"client_secret": "ui-secret"},
    )
    monkeypatch.setattr(services.live_source_service, "live_source_service", lambda: live)
    monkeypatch.setattr(
        "services.data_source_control_tower_service.live_source_service", lambda: live
    )
    monkeypatch.setattr(
        components.sidebar_navigation, "render_sidebar_navigation", lambda role: None
    )
    app = AppTest.from_file("pages/data_sources_connectors.py", default_timeout=20)
    _set_session(
        app,
        {
            "authenticated": True,
            "auth_backend": "local",
            "user": {"role": role},
            "role": role,
            "email": tenant_a.user_email,
            "user_id": tenant_a.user_id,
            "organization_id": tenant_a.organization_id,
            "organization_name": tenant_a.organization_name,
            "authorized_organization_ids": [tenant_a.organization_id],
        },
    )
    app.run()
    assert not app.exception
    text = " ".join(e.value for e in app.markdown) + repr([e.label for e in app.expander])
    assert all(provider in text for provider in ("AWS", "AZURE", "M365")), (
        text,
        [e.value for e in app.error],
        [e.value for e in app.warning],
    )
    assert "NEVER_SYNCED" in text and "Last Sync" in text
    assert "ui-secret" not in text
    assert len(app.dataframe) == 1
    if role == "client_admin":
        app.button(key=f"sync_{source_id}").click().run()
        assert not app.exception
        assert len(tower.get_execution_history(tenant_a, source_id)) == 2
        app.button(key=f"dis_{source_id}").click().run()
        assert not app.exception
        assert tower.get_source_detail(tenant_a, source_id).health == SourceHealth.DISABLED
        app.button(key=f"val_{source_id}").click().run()
        app.button(key=f"act_{source_id}").click().run()
        assert not app.exception
        assert tower.get_source_detail(tenant_a, source_id).active
        connector = active_source[1]
        connector.authenticate.side_effect = RuntimeError("Bearer ui-secret-provider-failure")
        app.button(key=f"sync_{source_id}").click().run()
        assert not app.exception
        assert tower.get_source_detail(tenant_a, source_id).health == SourceHealth.FAILED
        rendered = repr([e.value for e in app.markdown]) + repr([e.value for e in app.caption])
        rendered += repr([e.value for e in app.dataframe])
        assert "FAILED" in rendered
        assert "ui-secret" not in rendered and "Bearer" not in rendered
    else:
        assert not app.button
        assert not app.text_input
        with pytest.raises(PermissionError):
            tower.trigger_manual_sync(replace(tenant_a, role=role), source_id, "denied-ui")


def test_streamlit_missing_tenant_fails_closed(monkeypatch):
    from streamlit.testing.v1 import AppTest

    import components.sidebar_navigation
    import services.live_source_service

    monkeypatch.setattr(
        components.sidebar_navigation, "render_sidebar_navigation", lambda role: None
    )
    factory = MagicMock(side_effect=AssertionError("must not access source authority"))
    monkeypatch.setattr(services.live_source_service, "live_source_service", factory)
    app = AppTest.from_file("pages/data_sources_connectors.py")
    _set_session(app, {"authenticated": True, "role": "client_admin"})
    app.run()
    assert not app.exception
    assert any("No verified tenant context" in e.value for e in app.error)
    factory.assert_not_called()
    assert not app.button


def _set_session(app, values):
    for key, value in values.items():
        app.session_state[key] = value


def test_identical_queue_timestamps_keep_latest_counts_and_history(
    control_tower_setup, tenant_a, active_source
):
    tower, live, repo = control_tower_setup
    source_id, connector = active_source
    live.clock = lambda: datetime(2026, 9, 13, 10, tzinfo=timezone.utc)
    tower.trigger_manual_sync(tenant_a, source_id, "same-time-success")
    connector.authenticate.side_effect = RuntimeError("synthetic-provider-error")
    failed = tower.trigger_manual_sync(tenant_a, source_id, "same-time-failure")
    with repo.transaction() as db:
        db.execute(
            "UPDATE connector_executions SET records_rejected=3 WHERE execution_id=?",
            (failed["execution_id"],),
        )
    history = tower.get_execution_history(tenant_a, source_id)
    detail = tower.get_source_detail(tenant_a, source_id)
    assert history[0].execution_id == failed["execution_id"]
    assert detail.health == SourceHealth.FAILED
    assert detail.records_rejected == 3
    assert detail.last_sync_status == "FAILED"
