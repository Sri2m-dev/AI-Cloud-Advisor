import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz

from services.prospect_data_intake_service import ProspectTenant
from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.pilot.admission import admit_uploaded_evidence
from universal_evidence.product_closure import (
    DocumentResult,
    ProductClosureResult,
    analyze_document_bundle,
    answer_document_question,
)


def native_pdf(label="Invoice Number: INV-100"):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((40, 40), label)
    page.insert_text((40, 70), "Subtotal $100\nTax $20\nTotal Due $120")
    content = document.tobytes()
    document.close()
    return content


def tenant():
    now = datetime.now(timezone.utc)
    return ProspectTenant(
        "prospect", "audit", now.isoformat(), (now + timedelta(days=1)).isoformat(), 1
    )


def result():
    return ProductClosureResult(
        (
            DocumentResult(
                "invoice.xlsx",
                "XLSX",
                3,
                1,
                1,
                180,
                172,
                8,
                25,
                ("Sheet1!A1:D10",),
                (),
            ),
        ),
        10,
        5,
        180,
        172,
        8,
        25,
        "UNRESOLVED",
        "INSUFFICIENT_EVIDENCE",
        ("owner", "application", "cost center", "currency"),
        (
            {
                "representation_id": "representation-stable-1",
                "business_document_id": "business-document-stable-1",
            },
        ),
    )


def test_closure_round_trip_preserves_restart_view():
    original = result()
    persisted = json.loads(json.dumps(original.to_dict()))
    restored = ProductClosureResult.from_dict(persisted)
    assert restored == original
    assert restored.financial_documents[0]["representation_id"]
    assert restored.financial_documents[0]["business_document_id"]


def test_supported_answers_are_grounded_and_unknowns_are_not_inferred():
    licenses, provenance = answer_document_question("How many licenses?", result())
    spend, _ = answer_document_question("What is total spend?", result())
    owner, _ = answer_document_question("Who is the owner?", result())
    savings, _ = answer_document_question("What savings are available?", result())
    assert "180 purchased" in licenses and "8 unassigned" in licenses
    assert provenance == ("Sheet1!A1:D10",)
    assert "UNKNOWN" in spend and "currency" in spend
    assert owner.startswith("UNKNOWN")
    assert savings.startswith("Savings are UNKNOWN")


def test_pdf_only_can_anchor_governed_workspace_admission():
    admission = admit_uploaded_evidence(tenant(), filename="invoice.pdf", content=native_pdf())
    assert admission.original_filename == "invoice.pdf"
    assert admission.profile.container_format == "PDF"
    assert admission.regions == ()


def test_multiple_pdf_only_bundle_enters_document_pipeline_without_tabular_anchor():
    files = (("one.pdf", native_pdf("Invoice Number: INV-100")),)
    files += (("two.pdf", native_pdf("Invoice Number: INV-200")),)
    analyzed = analyze_document_bundle(
        context=EvidenceAnalysisContext("analysis", "source", "prospect", "org", "tenant"),
        files=files,
    )
    assert len(analyzed.documents) == 2
    assert all(item.container_type == "PDF" for item in analyzed.documents)
    assert all(item["representation_id"] for item in analyzed.financial_documents)
    assert all(item["business_document_id"] for item in analyzed.financial_documents)


def test_product_page_makes_document_intelligence_primary_and_has_no_anchor_rule():
    source = Path("pages/analyze_environment.py").read_text(encoding="utf-8")
    assert 'type=["csv", "xlsx", "pdf"]' in source
    assert "At least one CSV or XLSX file is required" not in source
    assert "Document Intelligence completed automatically" in source
    closure = source.index('closure = st.session_state.get("document_closure_result")')
    assert source.index("return", closure) < source.index("render_semantic_governance", closure)
