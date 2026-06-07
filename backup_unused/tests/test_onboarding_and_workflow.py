from database import db as db_module


def test_onboarding_persistence_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db_module, "SQLITE_DB_PATH", str(tmp_path / "onboarding.db"))

    # Unknown users should not be blocked.
    assert db_module.is_onboarding_complete("missing-user") is True

    db_module.add_user(
        username="client-user",
        password="secret",
        role="user",
        company="Acme Corp",
        user_type="client",
    )

    # Fresh users default to incomplete onboarding.
    assert db_module.is_onboarding_complete("client-user") is False

    db_module.mark_onboarding_complete("client-user")
    assert db_module.is_onboarding_complete("client-user") is True


def test_recommendation_workflow_transitions_and_permissions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db_module, "SQLITE_DB_PATH", str(tmp_path / "workflow.db"))

    # Same-company users with different roles.
    db_module.add_user("alice", "pw", "user", company="Acme Corp", user_type="client")
    db_module.add_user("bob", "pw", "premium", company="Acme Corp", user_type="client")
    db_module.add_user("eve", "pw", "user", company="Other Corp", user_type="client")

    recommendation_id = db_module.save_recommendation(
        username="alice",
        category="optimization",
        title="Rightsize compute",
        description="Downsize underutilized instances",
        source="optimization_insights",
        estimated_savings=1200,
    )

    # 1) Accept by creator user should work and auto-assign owner when unowned.
    accepted = db_module.update_recommendation_status(
        recommendation_id,
        "accepted",
        username="alice",
        notes="Accepted by owner candidate",
    )
    assert accepted is True

    items = db_module.list_recommendations(username="alice", limit=10)
    assert len(items) == 1
    assert items[0]["status"] == "accepted"
    assert items[0]["owner"] == "alice"

    # 2) Snooze by owner user should work.
    snoozed = db_module.update_recommendation_status(
        recommendation_id,
        "snoozed",
        username="alice",
        notes="Snoozed temporarily",
    )
    assert snoozed is True

    items = db_module.list_recommendations(username="alice", limit=10)
    assert items[0]["status"] == "snoozed"

    # 3) Complete by premium manager in same company should work.
    completed = db_module.update_recommendation_status(
        recommendation_id,
        "completed",
        username="bob",
        notes="Completed by manager",
    )
    assert completed is True

    items = db_module.list_recommendations(username="alice", limit=10)
    assert items[0]["status"] == "completed"
    assert items[0]["completed_at"] is not None

    # 4) Dismiss by outside-company user should fail.
    dismissed = db_module.update_recommendation_status(
        recommendation_id,
        "dismissed",
        username="eve",
        dismiss_reason="Not in my scope",
    )
    assert dismissed is False

    # Status remains unchanged after denied action.
    items = db_module.list_recommendations(username="alice", limit=10)
    assert items[0]["status"] == "completed"

    # Three successful status changes should have three events.
    events = db_module.list_recommendation_events(recommendation_id, limit=10)
    assert len(events) == 3
    assert {event["new_value"] for event in events} == {"accepted", "snoozed", "completed"}


def test_recommendation_detail_permissions_manager_vs_owner(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db_module, "SQLITE_DB_PATH", str(tmp_path / "workflow_details.db"))

    db_module.add_user("alice", "pw", "user", company="Acme Corp", user_type="client")
    db_module.add_user("bob", "pw", "premium", company="Acme Corp", user_type="client")
    db_module.add_user("charlie", "pw", "user", company="Acme Corp", user_type="client")

    recommendation_id = db_module.save_recommendation(
        username="alice",
        category="optimization",
        title="Tune storage tiering",
        description="Move infrequently accessed objects to cheaper storage classes",
        source="optimization_insights",
        estimated_savings=900,
    )

    # Make alice the owner first.
    accepted = db_module.update_recommendation_status(recommendation_id, "accepted", username="alice")
    assert accepted is True

    # Manager can reassign owner and change detail fields.
    manager_updated = db_module.update_recommendation_details(
        recommendation_id,
        username="bob",
        owner="charlie",
        priority="high",
        due_date="2026-03-30",
        notes="Reassigned to implementation owner",
    )
    assert manager_updated is True

    items = db_module.list_recommendations(username="alice", limit=10)
    assert items[0]["owner"] == "charlie"
    assert items[0]["priority"] == "high"
    assert items[0]["due_date"] == "2026-03-30"

    # Previous owner (non-manager, non-owner now) cannot edit details anymore.
    denied = db_module.update_recommendation_details(
        recommendation_id,
        username="alice",
        priority="low",
        notes="Should be denied",
    )
    assert denied is False

    # Current owner can edit details but cannot reassign owner without manager role.
    owner_updated = db_module.update_recommendation_details(
        recommendation_id,
        username="charlie",
        owner="alice",  # ignored for non-manager role
        priority="medium",
        notes="Owner updated details",
    )
    assert owner_updated is True

    items = db_module.list_recommendations(username="alice", limit=10)
    assert items[0]["owner"] == "charlie"
    assert items[0]["priority"] == "medium"

