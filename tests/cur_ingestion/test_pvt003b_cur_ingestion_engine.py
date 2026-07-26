import gzip
import io
from pathlib import Path

import pytest

from data_fabric.foundation import TenantContext
from data_fabric.foundation.exceptions import DataFabricTenantBoundaryError
from services.aws_cur_ingestion_engine import (
    CUR_FIELD_ALIASES,
    DEFAULT_CHUNK_SIZE,
    AccountMapping,
    AwsCurIngestionEngine,
    CurIngestionError,
    CurState,
    canonical_header_map,
    detect_profile,
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
UNDERSCORE_HEADERS = [
    "bill_payer_account_id",
    "line_item_usage_account_id",
    "bill_billing_period_start_date",
    "bill_billing_period_end_date",
    "line_item_usage_start_date",
    "line_item_usage_end_date",
    "product_servicecode",
    "line_item_product_code",
    "line_item_line_item_type",
    "line_item_unblended_cost",
    "line_item_currency_code",
    "line_item_blended_cost",
    "reservation_reservation_a_r_n",
    "savings_plan_savings_plan_a_r_n",
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


def underscore_cur(rows):
    return (
        ",".join(UNDERSCORE_HEADERS)
        + "\n"
        + "\n".join(",".join(values) for values in rows)
        + "\n"
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


@pytest.mark.parametrize("filename,compress", [("bom.csv", False), ("bom.csv.gz", True)])
def test_utf8_bom_never_corrupts_first_header(context, store, filename, compress):
    payload = b"\xef\xbb\xbf" + underscore_cur([row()])
    payload = gzip.compress(payload) if compress else payload
    result = engine(store).ingest(context, io.BytesIO(payload), filename)
    assert result.status is CurState.COMPLETED
    assert next(iter(store.imports.values()))["payer_account_id"] == "PAYER-A"


def test_slash_and_underscore_headers_are_semantically_equivalent(context, store):
    slash_store = store
    underscore_store = Store(store.mappings)
    slash = engine(slash_store).ingest(context, io.BytesIO(cur([row()])), "slash.csv")
    underscore = engine(underscore_store).ingest(
        context,
        io.BytesIO(underscore_cur([row()])),
        "underscore.csv",
    )
    slash_fact = next(iter(slash_store.facts.values()))
    underscore_fact = next(iter(underscore_store.facts.values()))
    comparable = {
        "payer_account_id",
        "member_account_id",
        "billing_period_start",
        "billing_period_end",
        "usage_start_at",
        "usage_end_at",
        "service_name",
        "product_code",
        "line_item_type",
        "currency_code",
        "unblended_cost",
        "blended_cost",
        "reservation_arn",
        "savings_plan_arn",
        "source_row_hash",
    }
    assert {key: slash_fact[key] for key in comparable} == {
        key: underscore_fact[key] for key in comparable
    }
    assert slash.normalized_total == underscore.normalized_total


def test_unmapped_optional_fields_remain_raw_and_protect_source_identity(context, store):
    headers = HEADERS + ["pricing_custom_optional"]
    first = row() + ["one"]
    second = row() + ["two"]
    payload = (
        ",".join(headers)
        + "\n"
        + ",".join(first)
        + "\n"
        + ",".join(second)
        + "\n"
    ).encode()
    result = engine(store).ingest(context, io.BytesIO(payload), "raw-identity.csv")
    assert result.duplicate_rows == 0
    assert len(store.facts) == 2
    assert {
        fact["raw_fields"]["pricing_custom_optional"]
        for fact in store.facts.values()
    } == {"one", "two"}


def test_actual_131_column_header_fixture_passes_profile_validation():
    fixture = Path(
        "tests/cur_ingestion/fixtures/aws_cur_normalized_131_headers.csv"
    )
    headers = fixture.read_text(encoding="utf-8-sig").strip().split(",")
    assert len(headers) == 131
    mapping = canonical_header_map(headers)
    profile = detect_profile(mapping)
    assert profile.payer == "payer_account_id"
    assert profile.currency == "currency_code"
    assert len(CUR_FIELD_ALIASES) == 28


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
