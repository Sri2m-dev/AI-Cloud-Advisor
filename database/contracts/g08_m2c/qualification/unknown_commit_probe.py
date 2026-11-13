"""UNEXECUTED real-driver probe for a separately authorized disposable local DB.

Uses a session temporary table, not an owner authorization or a technical PASS.
Simulates lost acknowledgement before/after commit; it does not emulate a real
network partition or qualify D10 reconciliation. Never imported by the application.
"""
import argparse
import json
import os
from uuid import uuid4


def require_local_target(authorization_reference):
    if (not authorization_reference or not authorization_reference.strip()
            or os.getenv("PGHOST") not in {"127.0.0.1", "::1"}
            or not os.getenv("PGDATABASE", "").startswith("nexora_m2c_")
            or os.getenv("NEXORA_LOCAL_QUALIFICATION_ACK") != "authorized-disposable-cluster"):
        raise ValueError("explicit authorized local disposable target required")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization-reference", required=True)
    args = parser.parse_args(argv)
    require_local_target(args.authorization_reference)
    # Standard managed libpq credentials only. Never print DSN/provider errors.
    import psycopg2
    from repositories.g08_transaction import G08DbapiTransaction
    from services.g08_transaction_boundary import CommitOutcomeUnknown, execute_once

    connection = None
    try:
        connection = psycopg2.connect()
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),inet_server_addr()::text")
            database, host = cursor.fetchone()
            if not database.startswith("nexora_m2c_") or host not in {"127.0.0.1", "::1"}:
                raise ValueError("actual target differs from approved local fixture")
            cursor.execute("CREATE TEMP TABLE g08_m2c_commit_probe(operation_id uuid PRIMARY KEY)")
        connection.commit()
        results = []
        for commit_reaches_server in (False, True):
            original_id = str(uuid4())

            class LostAcknowledgement(G08DbapiTransaction):
                def commit(self):
                    if commit_reaches_server:
                        super().commit()
                    else:
                        super().rollback()
                    raise TimeoutError("synthetic acknowledgement loss")

            tx = LostAcknowledgement(connection)

            def stage():
                tx.cursor.execute("INSERT INTO g08_m2c_commit_probe VALUES(%s)", (original_id,))
                return original_id

            try:
                execute_once(tx, stage)
                raise AssertionError("unacknowledged commit reported durable")
            except CommitOutcomeUnknown:
                pass
            with connection.cursor() as cursor:
                cursor.execute("SELECT EXISTS(SELECT 1 FROM g08_m2c_commit_probe WHERE operation_id=%s)", (original_id,))
                observed = cursor.fetchone()[0]
            connection.rollback()
            if observed is not commit_reaches_server:
                raise AssertionError("original operation reconciliation mismatch")
            results.append({"commit_reached_server": commit_reaches_server,
                            "client_outcome": "UNKNOWN", "original_id_visible": observed})
        print(json.dumps({"scope": "temporary-table driver probe, not G08 owner/D10 qualification", "results": results}))
        return 0
    except Exception:
        # Actual driver exceptions may include credentials or server metadata.
        print(json.dumps({"status": "DRIVER_PROBE_FAILED", "scope": "temporary-table driver probe"}))
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
