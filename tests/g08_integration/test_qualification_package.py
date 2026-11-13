"""Offline package preparation and explicit no-activation assertions."""
import json
from pathlib import Path
import pytest

from scripts.prepare_m2c_qualification import MIGRATIONS, prepare


def test_package_includes_all_six_in_order_and_never_executes_sql(tmp_path):
    result = prepare(tmp_path)
    assert result["status"] == "PREPARED_NOT_EXECUTED"
    assert result["postgresql_executed"] is False
    assert result["authorized_local_target_identified"] is False
    assessment = json.loads((tmp_path / "six-migration-compatibility.json").read_text())
    assert assessment["tables_defined"] == 15 and assessment["order_issues"] == []
    assert len(MIGRATIONS[:6]) == 6
    package = Path("database/contracts/g08_m2c/qualification/install_and_test.sql").read_text()
    assert package.index("tests/database_integrity") < package.index("S021_owner_authorization")
    assert "A022_result_link_integrity.sql" in package


def test_new_result_constraint_requires_nonnull_matching_event_id():
    sql = Path(MIGRATIONS[-1]).read_text()
    assert "(result->>'event_id') IS NOT NULL" in sql
    assert "result->>'event_id'=event_id::text" in sql
    assert "GRANT" not in sql


def test_new_source_is_not_silently_admitted_to_release_context():
    from scripts.audit_release_packaging import included
    rules = Path(".dockerignore").read_text()
    assert included("auth/authenticated_tenant.py", rules)
    assert not included("repositories/g08_transaction.py", rules)


@pytest.mark.parametrize("host,database,ack,reference", [
    ("remote.invalid","nexora_m2c_test","authorized-disposable-cluster","ref"),
    ("127.0.0.1","production","authorized-disposable-cluster","ref"),
    ("127.0.0.1","nexora_m2c_test","","ref"),
    ("127.0.0.1","nexora_m2c_test","authorized-disposable-cluster",""),
])
def test_driver_probe_rejects_missing_authorized_target_without_connecting(monkeypatch,host,database,ack,reference):
    from database.contracts.g08_m2c.qualification.unknown_commit_probe import require_local_target
    monkeypatch.setenv("PGHOST",host)
    monkeypatch.setenv("PGDATABASE",database)
    monkeypatch.setenv("NEXORA_LOCAL_QUALIFICATION_ACK",ack)
    with pytest.raises(ValueError): require_local_target(reference)
