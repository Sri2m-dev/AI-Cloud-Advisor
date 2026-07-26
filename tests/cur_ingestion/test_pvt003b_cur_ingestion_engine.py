import gzip
import io
from pathlib import Path

import pytest

from data_fabric.foundation import TenantContext
from data_fabric.foundation.exceptions import DataFabricTenantBoundaryError
from services.aws_cur_ingestion_engine import (
    DEFAULT_CHUNK_SIZE,
    AccountMapping,
    AwsCurIngestionEngine,
    CurIngestionError,
    CurState,
    file_sha256,
)

HEADERS = [
    "bill/PayerAccountId",
    "lineItem/UsageAccountId",
    "bill/BillingPeriodStartDate",
    "bill/BillingPeriodEndDate",
    "lineItem/UsageStartDate",
    "lineItem/UsageEndDate",
    "product/ProductName",
    "lineItem/ProductCode",
    "lineItem/LineItemType",
    "lineItem/UnblendedCost",
    "lineItem/CurrencyCode",
    "lineItem/BlendedCost",
    "reservation/ReservationARN",
    "savingsPlan/SavingsPlanARN",
]


def row(member="MEMBER-A", cost="1.25", payer="PAYER-A"):
    return [
        payer,
        member,
        "2026-07-01T00:00:00Z",
        "2026-07-31T23:59:59Z",
        "2026-07-02T00:00:00Z",
        "2026-07-02T01:00:00Z",
        "Amazon Elastic Compute Cloud",
        "AmazonEC2",
        "Usage",
        cost,
        "USD",
        "1.00",
        "arn:ri",
        "arn:sp",
    ]


def cur(rows):
    return (
        ",".join(HEADERS) + "\n" + "\n".join(",".join(values) for values in rows) + "\n"
    ).encode()


class Store:
    def __init__(self, mappings=()):
        self.mappings = tuple(mappings)
        self.imports = {}
        self.parts = {}
        self.facts = {}
        self.reconciliations = {}
        self.fail_facts = False

    def _scope(self, context, payload):
        assert payload["organization_id"] == context.organization_id
        assert payload["tenant_id"] == context.tenant_id

    def find_import(self, context, payer, file_hash):
        return next(
            (
                value
                for value in self.imports.values()
                if value["payer_account_id"] == payer and value["source_file_sha256"] == file_hash
            ),
            None,
        )

    def list_account_mappings(self, context):
        return self.mappings

    def create_import(self, context, payload):
        self._scope(context, payload)
        self.imports[payload["import_id"]] = dict(payload)

    def update_import(self, context, import_id, payload):
        self.imports[import_id].update(payload)

    def create_part(self, context, payload):
        self._scope(context, payload)
        self.parts[payload["import_part_id"]] = dict(payload)

    def update_part(self, context, part_id, payload):
        self.parts[part_id].update(payload)

    def write_facts(self, context, facts):
        if self.fail_facts:
            raise RuntimeError("synthetic batch write failure")
        written = 0
        for fact in facts:
            self._scope(context, fact)
            if fact["source_row_hash"] not in self.facts:
                self.facts[fact["source_row_hash"]] = dict(fact)
                written += 1
        return written

    def upsert_reconciliation(self, context, payload):
        self._scope(context, payload)
        self.reconciliations[payload["import_id"]] = dict(payload)


@pytest.fixture
def context():
    return TenantContext("org-a", "tenant-a")


@pytest.fixture
def store(context):
    return Store(
        (
            AccountMapping(
                context.organization_id, context.tenant_id, "PAYER-A", "PAYER-A", "active"
            ),
            AccountMapping(
                context.organization_id, context.tenant_id, "PAYER-A", "MEMBER-A", "active"
            ),
        )
    )


def engine(store):
    return AwsCurIngestionEngine(store, chunk_size=DEFAULT_CHUNK_SIZE)


def test_valid_csv_normalizes_cur_semantics_and_reconciles(context, store):
    result = engine(store).ingest(context, io.BytesIO(cur([row()])), "cur.csv")
    assert result.status is CurState.COMPLETED
    assert result.accepted_rows == 1 and result.normalized_total == 1.25
    fact = next(iter(store.facts.values()))
    assert fact["reservation_arn"] == "arn:ri" and fact["savings_plan_arn"] == "arn:sp"
    assert fact["raw_fields"]["lineItem/UnblendedCost"] == "1.25"
    assert store.reconciliations[result.import_id]["status"] == "reconciled"
    assert store.reconciliations[result.import_id]["source_cost_total"] == "1.25"


def test_gzip_is_supported_and_unsupported_type_is_rejected(context, store):
    compressed = gzip.compress(cur([row()]))
    assert (
        engine(store).ingest(context, io.BytesIO(compressed), "cur.csv.gz").status
        is CurState.COMPLETED
    )
    with pytest.raises(CurIngestionError, match="unsupported CUR format"):
        engine(Store()).ingest(context, io.BytesIO(b"x"), "cur.xlsx")


def test_profile_validation_and_billing_period_are_from_cur_not_upload_date(context, store):
    with pytest.raises(CurIngestionError, match="required field"):
        engine(store).ingest(context, io.BytesIO(b"a,b\n1,2\n"), "bad.csv")
    result = engine(store).ingest(context, io.BytesIO(cur([row()])), "billing.csv")
    persisted = store.imports[result.import_id]
    assert persisted["billing_period_start"] == "2026-07-01"
    assert persisted["billing_period_end"] == "2026-07-31"


def test_unknown_account_is_tenant_scoped_quarantine(context, store):
    result = engine(store).ingest(context, io.BytesIO(cur([row(member="UNKNOWN")])), "unknown.csv")
    assert result.status is CurState.AWAITING_ACCOUNT_RESOLUTION
    assert result.quarantined_rows == 1
    assert next(iter(store.facts.values()))["fact_status"] == "quarantined"


def test_foreign_mapping_and_mixed_payer_fail_closed(context, store):
    foreign = Store((AccountMapping("org-b", "tenant-b", "PAYER-A", "PAYER-A", "active"),))
    with pytest.raises(DataFabricTenantBoundaryError):
        engine(foreign).ingest(context, io.BytesIO(cur([row()])), "foreign.csv")
    with pytest.raises(CurIngestionError, match="mixed-payer"):
        engine(store).ingest(context, io.BytesIO(cur([row(), row(payer="PAYER-B")])), "mixed.csv")


def test_file_hash_duplicate_replays_without_duplicate_facts(context, store):
    payload = cur([row()])
    first = engine(store).ingest(context, io.BytesIO(payload), "duplicate.csv")
    second = engine(store).ingest(context, io.BytesIO(payload), "duplicate.csv")
    assert second.replayed and second.import_id == first.import_id and len(store.facts) == 1
    assert file_sha256(io.BytesIO(payload)) == store.imports[first.import_id]["source_file_sha256"]


def test_duplicate_source_rows_are_idempotent_and_checkpointed(context, store):
    result = engine(store).ingest(context, io.BytesIO(cur([row(), row()])), "rows.csv")
    assert result.duplicate_rows == 1 and len(store.facts) == 1
    part = next(iter(store.parts.values()))
    assert part["checkpoint_row"] == 2 and part["status"] == "completed"


def test_service_adapter_uses_the_pvt003a_source_hash_idempotency_constraint():
    source = Path("repositories/aws_cur_ingestion_repository.py").read_text(encoding="utf-8")
    assert "organization_id,tenant_id,import_id,source_row_hash" in source


def test_batch_failure_marks_import_failed_and_is_reconstructable(context, store):
    store.fail_facts = True
    with pytest.raises(RuntimeError, match="batch write"):
        engine(store).ingest(context, io.BytesIO(cur([row()])), "failure.csv")
    persisted = next(iter(store.imports.values()))
    assert persisted["status"] == CurState.FAILED and persisted["failure_code"] == "RuntimeError"


def test_retry_resumes_the_same_failed_import_with_stable_part_and_fact_identity(context, store):
    payload = cur([row()])
    store.fail_facts = True
    with pytest.raises(RuntimeError):
        engine(store).ingest(context, io.BytesIO(payload), "retry.csv")
    failed_import = next(iter(store.imports))
    store.fail_facts = False
    resumed = engine(store).ingest(context, io.BytesIO(payload), "retry.csv")
    assert resumed.import_id == failed_import
    assert resumed.status is CurState.COMPLETED
    assert len(store.parts) == 1 and len(store.facts) == 1


def test_large_synthetic_cur_is_chunked_without_whole_file_rows(context, store):
    rows = [row(cost="0.01") for _ in range(DEFAULT_CHUNK_SIZE + 3)]
    result = engine(store).ingest(context, io.BytesIO(cur(rows)), "large.csv")
    assert result.source_rows == DEFAULT_CHUNK_SIZE + 3
    assert len(store.parts) == 2
    assert (
        max(part["row_end"] - part["row_start"] + 1 for part in store.parts.values())
        == DEFAULT_CHUNK_SIZE
    )


def test_corrected_file_and_late_part_are_distinct_deterministic_imports(context, store):
    first = engine(store).ingest(context, io.BytesIO(cur([row(cost="1")])), "original.csv")
    corrected = engine(store).ingest(
        context,
        io.BytesIO(cur([row(cost="2")])),
        "corrected.csv",
        supersedes_import_id=first.import_id,
    )
    assert corrected.import_id != first.import_id
    assert store.imports[corrected.import_id]["supersedes_import_id"] == first.import_id
