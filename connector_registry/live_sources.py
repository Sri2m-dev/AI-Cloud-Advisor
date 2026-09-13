"""Durable control metadata extending the existing CMP-P4 source authority."""

from contextlib import contextmanager
from pathlib import Path

from data_fabric.source_facts.persistence import SQLiteSourceFactRepository

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations/connectors/0001_live_source_control.sql"
)


class BoundSourceFactRepository(SQLiteSourceFactRepository):
    """Join source publication to the caller's control-plane transaction."""

    def __init__(self, database, connection):
        self.database, self.connection = database, connection

    @contextmanager
    def transaction(self):
        yield self.connection

    def instance_enabled(self, organization_id, tenant_id, source_instance_id):
        row = self.connection.execute(
            "SELECT enabled FROM source_instances WHERE organization_id=? "
            "AND tenant_id=? AND source_instance_id=?",
            (organization_id, tenant_id, source_instance_id),
        ).fetchone()
        return bool(row and row[0])


class LiveSourceRepository(SQLiteSourceFactRepository):
    """SQLite durable deployment, matching the v1 SourceFact storage contract."""

    def __init__(self, database):
        super().__init__(database)
        with self.transaction() as db:
            # Statements are additive and replay-safe. Do not use executescript:
            # it would commit the surrounding transaction implicitly.
            for statement in MIGRATION.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    db.execute(statement)

    @contextmanager
    def transaction(self):
        with super().transaction() as db:
            yield db

    @staticmethod
    def source(db, context, source_id):
        row = db.execute(
            "SELECT * FROM connector_source_config WHERE organization_id=? "
            "AND tenant_id=? AND source_id=?",
            (context.organization_id, context.tenant_id, source_id),
        ).fetchone()
        if row is None:
            raise PermissionError("Source is unavailable in this tenant")
        return dict(row)

    def bound(self, db):
        return BoundSourceFactRepository(self.database, db)
