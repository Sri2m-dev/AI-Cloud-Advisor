"""Static artifact assertions only: no SQL parser or PostgreSQL execution."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "database/contracts/g08_m2b"
STRUCTURE = (SQL / "S021_owner_authorization.sql").read_text()
CHECKER = (SQL / "A021_owner_integrity.sql").read_text()
INTERFACES = (SQL / "A021_owner_interfaces.sql").read_text()


def test_every_new_table_has_privilege_rls_immutability_lock_and_consistency_inventory():
    tables = re.findall(r"CREATE TABLE public\.(g08_\w+)", STRUCTURE)
    assert len(tables) == len(set(tables)) == 4
    for table in tables:
        assert STRUCTURE.count(f"'{table}'") == 2
        assert CHECKER.count(f"'{table}'") >= 3
    assert "ENABLE ROW LEVEL SECURITY" in STRUCTURE and "FORCE ROW LEVEL SECURITY" in STRUCTURE
    assert "BEFORE TRUNCATE" in CHECKER and "BEFORE INSERT OR UPDATE OR DELETE" in CHECKER
    assert "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW" in CHECKER


def test_terminal_chain_and_no_mutable_consumed_flags():
    assert "predecessor_revision=revision-1" in STRUCTURE
    assert "previous.status<>'ADMITTED'" in CHECKER
    assert "s.predecessor_status_id IS DISTINCT FROM previous.status_id" in CHECKER
    assert "s.approval_manifest IS DISTINCT FROM manifest" in CHECKER
    assert "n=0" in CHECKER
    assert "owner_operation_id uuid PRIMARY KEY" in STRUCTURE
    assert "UNIQUE(evidence_id,authorization_id,owner_operation_id,event_id)" in STRUCTURE
    assert "g08_owner_evidence_consumption_fk" in STRUCTURE
    assert "consumed boolean" not in STRUCTURE


def test_deferred_checker_is_read_only_and_separately_scoped():
    body = CHECKER.split("CREATE FUNCTION public.g08_assert_owner_history()", 1)[1].split("END $$;", 1)[0]
    code = re.sub(r"--[^\n]*", "", body)
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|EXECUTE)\b", code, re.I)
    assert "SECURITY DEFINER" in body and "SET search_path=pg_catalog SET row_security=on" in body
    assert "PERFORM public.g08_assert_identity_history()" in body
    assert "NOT pol.polpermissive" in body
    assert "EXCEPTION WHEN" not in body


def test_real_trust_interfaces_are_closed_without_success_fallback():
    verifier = INTERFACES.split("CREATE FUNCTION public.g08_verify_owner_trust", 1)[1].split("END $$;", 1)[0]
    assert "IDENTITY_ASSURANCE_UNAVAILABLE" in verifier
    assert "RETURN" not in verifier.split("AS $$", 1)[1]
    assert "GRANT INSERT" not in STRUCTURE + CHECKER + INTERFACES
    assert "GRANT UPDATE" not in STRUCTURE + CHECKER + INTERFACES
    assert "FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner,nxr_g08_owner_fn_owner" in INTERFACES


def test_current_state_reads_and_clock_are_after_global_lock():
    body = INTERFACES.split("CREATE FUNCTION public.g08_owner_decision_time", 1)[1].split("END $$;", 1)[0]
    assert body.index("PERFORM public.g08_lock_identity_history()") < body.index("SELECT * INTO STRICT a")
    assert body.index("INTO already_consumed") < body.index("decision_time:=pg_catalog.clock_timestamp()")
    assert "s.status<>'ADMITTED'" in body and "already_consumed" in body
    assert "a.valid_to<=decision_time" in body and "identity.db_session_user" in body


def test_history_receipts_and_proof_are_checked_both_directions():
    assert "G08 incomplete owner consumption/evidence" in CHECKER
    assert "terminal.occurred_at<=consumption.consumed_at" in CHECKER
    assert "proof.result IS DISTINCT FROM receipt.result" in CHECKER
    assert "operator_assertion.purpose<>'EXECUTION'" in CHECKER
    assert "proof.request_digest<>event.request_digest" in CHECKER
    assert "current expiry never erases history" in CHECKER
