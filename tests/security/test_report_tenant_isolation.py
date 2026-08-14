from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

from backend.services import report_service


class _Query:
    def __init__(self) -> None:
        self.limit_value = None

    def limit(self, value: int):
        self.limit_value = value
        return self

    def execute(self):
        return SimpleNamespace(data=[{"org_id": "tenant-a", "value": 1}])


def test_report_helper_scopes_every_table_read(monkeypatch) -> None:
    calls = []
    query = _Query()

    def scoped(client, table_name, tenant_id):
        calls.append((client, table_name, tenant_id))
        return query

    monkeypatch.setattr(report_service, "scoped_query", scoped)

    rows = report_service._fetch_rows("mart_executive_summary", "tenant-a", limit=7)

    assert rows == [{"org_id": "tenant-a", "value": 1}]
    assert calls == [(report_service.supabase, "mart_executive_summary", "tenant-a")]
    assert query.limit_value == 7


def test_report_history_payload_contains_tenant_scope(monkeypatch) -> None:
    captured = {}

    class Table:
        def insert(self, payload):
            captured.update(payload)
            return self

        def execute(self):
            return SimpleNamespace(data=[captured])

    fake_client = SimpleNamespace(table=lambda table_name: Table())
    monkeypatch.setattr(report_service, "supabase", fake_client)

    result = report_service.record_report_history(
        "tenant-a",
        "Board Pack",
        "cio@example.com",
        "ui",
        "generated",
    )

    assert result["saved"] is True
    assert captured["org_id"] == "tenant-a"


def test_governed_office_exports_are_valid_packages(monkeypatch) -> None:
    payload = {
        "spend": {"total_spend": 1200.0},
        "budget": {"budget": 1500.0, "actual": 1200.0, "variance": -300.0},
        "forecast": 1350.0,
        "recommendations": {
            "items": [{"title": "Retire duplicate tool", "status": "PENDING"}],
            "count": 1,
            "realized_savings": 0.0,
            "pending_savings": 300.0,
            "total_savings": 300.0,
        },
        "saas": {"saas_spend": 200.0},
        "approvals": {"PENDING": 1, "TOTAL": 1},
        "audit": {"events": 4, "event_types": 2},
    }
    monkeypatch.setattr(report_service, "_executive_export_payload", lambda tenant: payload)

    xlsx = report_service.build_report_xlsx("Evidence", "tenant-a", "cio@example.com")
    pptx = report_service.build_board_pack_pptx("tenant-a", "cio@example.com")

    assert xlsx.startswith(b"PK")
    assert pptx.startswith(b"PK")
    with ZipFile(BytesIO(xlsx)) as workbook:
        assert b"tenant-a" in workbook.read("xl/sharedStrings.xml")
    with ZipFile(BytesIO(pptx)) as presentation:
        assert b"tenant-a" in presentation.read("ppt/slides/slide1.xml")
