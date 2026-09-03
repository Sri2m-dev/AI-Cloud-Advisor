from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal


class FinancialPublicationError(RuntimeError):
    pass


class CanonicalFinancialRepository:
    """SQLite-backed canonical publication consumed by EnterpriseSpendService."""

    def __init__(self, database, *, kill_switch=False):
        self.database = str(database)
        self.kill_switch = kill_switch
        self._migrate()

    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate(self):
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS canonical_financial_observations (
                observation_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL, prospect_id TEXT NOT NULL, analysis_id TEXT NOT NULL,
                source_id TEXT NOT NULL, file_id TEXT NOT NULL, sheet_id TEXT NOT NULL,
                row_number INTEGER NOT NULL, field TEXT NOT NULL, domain_decision TEXT NOT NULL,
                semantic_decision TEXT NOT NULL, normalization_run_id TEXT NOT NULL,
                measure_authority TEXT NOT NULL, currency_authority TEXT NOT NULL,
                financial_classification TEXT NOT NULL, amount TEXT NOT NULL,
                currency TEXT NOT NULL, dimensions TEXT NOT NULL,
                reconciliation_evidence TEXT NOT NULL, publication_fingerprint TEXT NOT NULL,
                version INTEGER NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(organization_id, tenant_id, analysis_id, publication_fingerprint)
            )""")

    @staticmethod
    def _scope(context):
        if not getattr(context, "organization_id", None) or not getattr(context, "tenant_id", None):
            raise TypeError("AuthenticatedTenantContext is required")
        return context.organization_id, context.tenant_id

    def publish(self, observations, context):
        if self.kill_switch:
            raise FinancialPublicationError("financial publication blocked by kill switch")
        organization_id, tenant_id = self._scope(context)
        rows = tuple(observations)
        if any(
            row.organization_id != organization_id or row.tenant_id != tenant_id for row in rows
        ):
            raise FinancialPublicationError("cross-tenant financial publication rejected")
        with self._connect() as conn:
            for row in rows:
                conn.execute(
                    """INSERT OR IGNORE INTO canonical_financial_observations VALUES
                    (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        row.observation_id,
                        row.organization_id,
                        row.tenant_id,
                        row.prospect_id,
                        row.analysis_id,
                        row.source_id,
                        row.file_id,
                        row.sheet_id,
                        row.row_number,
                        row.field,
                        row.domain_decision,
                        row.semantic_decision,
                        row.normalization_run_id,
                        row.measure_authority,
                        row.currency_authority,
                        row.financial_classification,
                        str(row.amount),
                        row.currency,
                        json.dumps(dict(row.dimensions), sort_keys=True),
                        json.dumps(row.reconciliation_evidence),
                        row.publication_fingerprint,
                        row.version,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        return len(rows)

    def _filtered(self, context):
        organization_id, tenant_id = self._scope(context)
        with self._connect() as conn:
            return tuple(
                conn.execute(
                    "SELECT * FROM canonical_financial_observations "
                    "WHERE organization_id=? AND tenant_id=?",
                    (organization_id, tenant_id),
                ).fetchall()
            )

    def get_posture(self, context, period_start=None, period_end=None):
        rows = self._filtered(context)
        if not rows:
            return None
        currencies = {row["currency"] for row in rows}
        if len(currencies) != 1:
            raise FinancialPublicationError("mixed currencies cannot form one posture")
        total = sum((Decimal(row["amount"]) for row in rows), Decimal("0"))
        return {
            "organization_id": context.organization_id,
            "currency": next(iter(currencies)),
            "generated_at": datetime.now(timezone.utc),
            "import_count": 1,
            "latest_import_id": rows[0]["analysis_id"],
            "latest_import_status": "PUBLISHED",
            "source_rows": len(rows),
            "persisted_facts": len(rows),
            "total_ingested_spend": total,
            "cloud_spend": total,
            "resolved_spend": total,
            "quarantined_spend": Decimal("0"),
            "allocated_spend": Decimal("0"),
            "unallocated_resolved_spend": total,
            "reconciled_spend": total,
            "unreconciled_spend": Decimal("0"),
            "reconciliation_status": "reconciled",
            "reconciliation_variance": Decimal("0"),
        }

    def _breakdown(self, context, dimension):
        totals = {}
        refs = {}
        for row in self._filtered(context):
            value = json.loads(row["dimensions"]).get(dimension, "UNKNOWN")
            totals[value] = totals.get(value, Decimal("0")) + Decimal(row["amount"])
            refs.setdefault(value, []).append(row["observation_id"])
        return (
            tuple(
                {
                    dimension: key,
                    "amount": value,
                    "currency": self._filtered(context)[0]["currency"],
                    "observation_ids": tuple(refs[key]),
                }
                for key, value in sorted(totals.items())
            )
            if totals
            else ()
        )

    def get_spend_by_service(self, context, period_start=None, period_end=None):
        return self._breakdown(context, "service")

    def get_spend_by_region(self, context, period_start=None, period_end=None):
        return self._breakdown(context, "region")

    def get_account_posture(self, context, period_start=None, period_end=None):
        return ()

    def get_account_classification_evidence(self, context, account_id):
        return ()

    def get_accounts_classification_evidence(self, context, account_ids):
        return ()

    def get_import_history(self, context):
        return ()

    def purge_analysis(self, context, analysis_id):
        organization_id, tenant_id = self._scope(context)
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM canonical_financial_observations "
                "WHERE organization_id=? AND tenant_id=? AND analysis_id=?",
                (organization_id, tenant_id, analysis_id),
            )
        return cursor.rowcount
