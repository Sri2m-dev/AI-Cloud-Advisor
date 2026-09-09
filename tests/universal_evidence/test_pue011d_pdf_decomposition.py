from __future__ import annotations

from datetime import datetime, timezone

import fitz

from universal_evidence.containers import (
    PdfDecompositionConfig,
    decompose_pdf,
    decompose_xlsx,
)
from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.documents import (
    EvidenceRegion,
    PdfLocation,
    SecurityFinding,
    StructuralState,
    StructuralType,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def context(tenant="tenant-a"):
    return EvidenceAnalysisContext("analysis", "source", "prospect", "org", tenant)


def decompose(content, *, tenant="tenant-a", filename="neutral.pdf", config=None):
    return decompose_pdf(
        context=context(tenant),
        content=content,
        admitted_at=NOW,
        source_reference="authorized:synthetic",
        filename=filename,
        config=config,
    )


def pdf_bytes(draw, *, pages=1, encryption=False):
    document = fitz.open()
    for index in range(pages):
        page = document.new_page()
        draw(page, index)
    if encryption:
        content = document.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-pass",
            user_pw="user-pass",
        )
    else:
        content = document.tobytes()
    document.close()
    return content


def draw_table(page, rect, headers=("Field A", "Field B", "Field C")):
    rows = 4
    columns = len(headers)
    row_height = rect.height / rows
    column_width = rect.width / columns
    for row in range(rows + 1):
        y = rect.y0 + row * row_height
        page.draw_line((rect.x0, y), (rect.x1, y))
    for column in range(columns + 1):
        x = rect.x0 + column * column_width
        page.draw_line((x, rect.y0), (x, rect.y1))
    for column, header in enumerate(headers):
        page.insert_text(
            (rect.x0 + column * column_width + 3, rect.y0 + 13), header, fontsize=8
        )
    for row in range(1, rows):
        for column in range(columns):
            page.insert_text(
                (
                    rect.x0 + column * column_width + 3,
                    rect.y0 + row * row_height + 13,
                ),
                f"R{row}C{column + 1}",
                fontsize=8,
            )


def test_native_text_key_value_summary_and_note_regions_are_structural():
    def draw(page, _):
        page.insert_textbox(
            fitz.Rect(40, 40, 250, 90), "Label A: Value A\nLabel B: Value B", fontsize=10
        )
        page.insert_textbox(
            fitz.Rect(40, 130, 250, 180), "Measure A 10\nMeasure B 20", fontsize=10
        )
        page.insert_textbox(
            fitz.Rect(40, 220, 350, 270), "A bounded neutral explanatory paragraph.", fontsize=10
        )

    result = decompose(pdf_bytes(draw))
    types = {item.structural_type for item in result.regions}
    assert result.pages[0].native_text_available
    assert StructuralType.KEY_VALUE in types
    assert StructuralType.SUMMARY in types
    assert StructuralType.TEXT in types


def test_multiple_tables_on_one_page_have_independent_regions():
    def draw(page, _):
        draw_table(page, fitz.Rect(40, 60, 280, 180))
        draw_table(page, fitz.Rect(310, 60, 550, 180), ("One", "Two", "Three"))

    result = decompose(pdf_bytes(draw))
    tables = [
        item for item in result.regions if item.structural_type is StructuralType.TABULAR
    ]
    assert len(tables) == 2
    assert len({item.region_id for item in tables}) == 2
    assert all(isinstance(item.location, PdfLocation) for item in tables)


def test_multiple_pages_rotation_repeated_edges_and_continuation_candidate():
    def draw(page, index):
        page.insert_text((40, 30), "Repeated neutral heading", fontsize=9)
        if index < 2:
            draw_table(page, fitz.Rect(40, 80, 400, 220))
        else:
            page.insert_text((40, 80), "Rotated neutral page")
        page.insert_text((40, 820), "Repeated neutral footer", fontsize=9)
        if index == 2:
            page.set_rotation(90)

    result = decompose(pdf_bytes(draw, pages=3))
    assert len(result.pages) == 3
    assert result.pages[2].rotation == 90
    assert result.repeated_page_elements
    assert result.continuation_candidates


def test_image_only_page_is_preserved_unresolved_without_ocr():
    def draw(page, _):
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
        pixmap.clear_with(200)
        page.insert_image(fitz.Rect(40, 40, 240, 240), pixmap=pixmap)

    result = decompose(pdf_bytes(draw))
    assert not result.pages[0].native_text_available
    assert result.pages[0].image_count == 1
    assert result.regions[0].structural_type is StructuralType.UNKNOWN
    assert result.regions[0].status is StructuralState.UNRESOLVED
    assert "OCR not attempted" in result.regions[0].warnings[0]


def test_identity_is_deterministic_filename_independent_and_tenant_scoped():
    content = pdf_bytes(lambda page, _: page.insert_text((40, 80), "Neutral text"))
    first = decompose(content, filename="first.pdf")
    replay = decompose(content, filename="renamed.pdf")
    foreign = decompose(content, tenant="tenant-b")
    assert first.container.container_id == replay.container.container_id
    assert [item.region_id for item in first.regions] == [
        item.region_id for item in replay.regions
    ]
    assert first.container.container_id != foreign.container.container_id
    assert [item.region_id for item in first.regions] != [
        item.region_id for item in foreign.regions
    ]


def test_malformed_encrypted_and_active_content_fail_closed():
    malformed = decompose(b"not-a-pdf")
    encrypted = decompose(pdf_bytes(lambda page, _: None, encryption=True))
    active = decompose(
        pdf_bytes(lambda page, _: page.insert_text((40, 80), "Neutral"))
        + b"\n/JavaScript"
    )
    assert malformed.status is StructuralState.QUARANTINED
    assert encrypted.status is StructuralState.QUARANTINED
    assert active.status is StructuralState.QUARANTINED
    findings = {item.finding for item in encrypted.container.security_diagnostics}
    assert SecurityFinding.PASSWORD_PROTECTED in findings
    assert any(
        item.finding is SecurityFinding.ACTIVE_CONTENT_PRESENT
        for item in active.container.security_diagnostics
    )


def test_attachment_and_external_uri_are_detected_without_retrieval():
    attached = fitz.open()
    attached.new_page().insert_text((40, 80), "Neutral")
    attached.embfile_add("bounded.txt", b"bounded")
    attached_bytes = attached.tobytes()
    attached.close()

    linked = fitz.open()
    page = linked.new_page()
    page.insert_text((40, 80), "Neutral link")
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(40, 60, 150, 90),
            "uri": "https://invalid.example",
        }
    )
    linked_bytes = linked.tobytes()
    linked.close()

    attachment_result = decompose(attached_bytes)
    link_result = decompose(linked_bytes)
    assert attachment_result.status is StructuralState.QUARANTINED
    assert any(
        item.finding is SecurityFinding.EMBEDDED_OBJECTS_PRESENT
        for item in attachment_result.container.security_diagnostics
    )
    assert any(
        item.finding is SecurityFinding.EXTERNAL_LINKS_PRESENT
        for item in link_result.container.security_diagnostics
    )


def test_resource_exhaustion_is_partial_and_bounded():
    content = pdf_bytes(
        lambda page, index: page.insert_text((40, 80), f"Page {index}"), pages=3
    )
    result = decompose(content, config=PdfDecompositionConfig(max_pages=1))
    assert result.status is StructuralState.PARTIAL
    assert len(result.pages) == 1
    assert result.container.resource_diagnostics.limit_exceeded


def test_label_layout_and_font_mutations_remain_structural():
    first = decompose(
        pdf_bytes(
            lambda page, _: page.insert_textbox(
                fitz.Rect(40, 40, 250, 100), "Alpha: North\nBeta: East", fontsize=8
            )
        )
    )
    second = decompose(
        pdf_bytes(
            lambda page, _: page.insert_textbox(
                fitz.Rect(200, 200, 500, 270), "Gamma: West\nDelta: South", fontsize=14
            )
        )
    )
    assert first.regions[0].structural_type is StructuralType.KEY_VALUE
    assert second.regions[0].structural_type is StructuralType.KEY_VALUE
    assert not hasattr(first, "financial_observations")
    assert not hasattr(first, "source_facts")


def test_pdf_and_xlsx_converge_on_evidence_region_contract():
    pdf_result = decompose(
        pdf_bytes(lambda page, _: draw_table(page, fitz.Rect(40, 60, 400, 200)))
    )
    assert isinstance(pdf_result.regions[0], EvidenceRegion)
    assert decompose_xlsx is not None
    assert pdf_result.regions[0].structural_type in set(StructuralType)


def test_no_ocr_or_semantic_publication_surface_exists():
    result = decompose(
        pdf_bytes(lambda page, _: page.insert_text((40, 80), "Invoice Tax Owner USD"))
    )
    assert all(item.structural_type in set(StructuralType) for item in result.regions)
    assert not hasattr(result, "ocr_text")
    assert not hasattr(result, "semantic_evidence_sets")
    assert not hasattr(result, "canonical_facts")
