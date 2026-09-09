"""Safe native-text PDF structural decomposition using PyMuPDF."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, fields
from datetime import datetime
from time import perf_counter

import fitz

from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.documents import (
    EvidenceRegion,
    PdfLocation,
    ResourceDiagnostics,
    SecurityDiagnostic,
    SecurityFinding,
    StructuralLineage,
    StructuralState,
    StructuralType,
    UploadContainer,
    structural_fingerprint,
)

PDF_DECOMPOSITION_VERSION = "pue-011d.pdf.v1"


@dataclass(frozen=True, slots=True)
class PdfDecompositionConfig:
    max_file_size: int = 25 * 1024 * 1024
    max_pages: int = 250
    max_text_characters: int = 5_000_000
    max_text_blocks: int = 100_000
    max_images: int = 10_000
    max_annotations: int = 25_000
    max_forms: int = 25_000
    max_tables: int = 500
    max_regions: int = 250
    max_processing_seconds: float = 30.0
    max_excerpt_length: int = 160

    def __post_init__(self) -> None:
        if any(getattr(self, item.name) <= 0 for item in fields(self)):
            raise ValueError("PDF decomposition limits must be positive")


@dataclass(frozen=True, slots=True)
class PdfRegionProfile:
    block_count: int
    line_count: int
    row_count: int | None
    column_count: int | None
    candidate_headers: tuple[str, ...]
    font_sizes: tuple[float, ...]
    bounded_excerpt: str | None
    image_count: int = 0


@dataclass(frozen=True, slots=True)
class PageObservation:
    page_id: str
    page_number: int
    width: float
    height: float
    rotation: int
    native_text_available: bool
    text_character_count: int
    text_block_count: int
    table_count: int
    image_count: int
    annotation_count: int
    form_field_count: int
    warnings: tuple[str, ...]
    region_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PdfDecomposition:
    container: UploadContainer
    decomposition_version: str
    pages: tuple[PageObservation, ...]
    documents: tuple = ()
    regions: tuple[EvidenceRegion, ...] = ()
    region_profiles: tuple[tuple[str, PdfRegionProfile], ...] = ()
    continuation_candidates: tuple[tuple[str, str], ...] = ()
    repeated_page_elements: tuple[str, ...] = ()
    status: StructuralState = StructuralState.DISCOVERED
    warnings: tuple[str, ...] = ()


def decompose_pdf(
    *,
    context: EvidenceAnalysisContext,
    content: bytes,
    admitted_at: datetime,
    source_reference: str,
    filename: str | None = None,
    config: PdfDecompositionConfig | None = None,
) -> PdfDecomposition:
    """Observe native PDF structure without OCR or semantic promotion."""
    policy = config or PdfDecompositionConfig()
    fingerprint = hashlib.sha256(content).hexdigest()
    initial_findings = _byte_security_findings(content)
    size_limited = len(content) > policy.max_file_size
    malformed_signature = b"%PDF-" not in content[:1024]
    if malformed_signature:
        initial_findings += (
            SecurityDiagnostic(SecurityFinding.MALFORMED, "PDF signature not observed"),
        )
    state = (
        StructuralState.QUARANTINED
        if malformed_signature or _dangerous(initial_findings)
        else StructuralState.PARTIAL
        if size_limited
        else StructuralState.DISCOVERED
    )
    reason = "file size limit reached" if size_limited else None
    container = _container(
        context,
        fingerprint,
        len(content),
        admitted_at,
        source_reference,
        filename,
        state,
        initial_findings,
        ResourceDiagnostics(
            len(content), limit_exceeded=size_limited, partial_reason=reason
        ),
        ((reason,) if reason else ()),
    )
    if state is not StructuralState.DISCOVERED:
        return PdfDecomposition(
            container,
            PDF_DECOMPOSITION_VERSION,
            (),
            status=state,
            warnings=container.warnings,
        )
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError):
        return _quarantined(container, SecurityFinding.MALFORMED, "PDF could not be opened")
    try:
        if document.needs_pass:
            finding = SecurityDiagnostic(
                SecurityFinding.PASSWORD_PROTECTED,
                "password-protected PDF cannot be structurally opened",
            )
            updated = _updated_container(
                container, StructuralState.QUARANTINED, (finding,), None, ()
            )
            return PdfDecomposition(
                updated,
                PDF_DECOMPOSITION_VERSION,
                (),
                status=StructuralState.QUARANTINED,
            )
        return _decompose_document(document, container, policy)
    finally:
        document.close()


def _decompose_document(document, container, policy):
    started = perf_counter()
    findings = list(container.security_diagnostics)
    if document.embfile_count() > 0:
        findings.append(
            SecurityDiagnostic(
                SecurityFinding.EMBEDDED_OBJECTS_PRESENT,
                "embedded PDF attachment observed",
            )
        )
        updated = _updated_container(
            container, StructuralState.QUARANTINED, tuple(findings), None, ()
        )
        return PdfDecomposition(
            updated,
            PDF_DECOMPOSITION_VERSION,
            (),
            status=StructuralState.QUARANTINED,
        )
    pages: list[PageObservation] = []
    regions: list[EvidenceRegion] = []
    profiles: list[tuple[str, PdfRegionProfile]] = []
    page_edge_text: dict[str, list[int]] = {}
    total_text = total_blocks = total_tables = total_images = 0
    total_annotations = total_forms = 0
    limited = len(document) > policy.max_pages
    limit_reason = "page limit reached" if limited else None
    for page_index in range(min(len(document), policy.max_pages)):
        if perf_counter() - started > policy.max_processing_seconds:
            limited = True
            limit_reason = "PDF processing time limit reached"
            break
        page = document[page_index]
        page_id = f"{container.container_id}:page:{page_index + 1}"
        page_warnings: list[str] = []
        page_regions_start = len(regions)
        blocks = page.get_text("blocks", sort=True)
        text_blocks = [item for item in blocks if len(item) >= 7 and item[6] == 0]
        image_rects = _image_rects(page)
        text_count = sum(len(str(item[4])) for item in text_blocks)
        total_text += text_count
        total_blocks += len(text_blocks)
        total_images += len(image_rects)
        links = page.get_links()
        annotations = tuple(page.annots() or ())
        widgets = tuple(page.widgets() or ())
        total_annotations += len(annotations) + len(links)
        total_forms += len(widgets)
        if any(link.get("uri") or link.get("file") for link in links):
            findings.append(
                SecurityDiagnostic(
                    SecurityFinding.EXTERNAL_LINKS_PRESENT,
                    "external PDF action observed; retrieval disabled",
                )
            )
        tables = _find_tables(page)
        total_tables += len(tables)
        if _limits_exceeded(
            policy,
            total_text,
            total_blocks,
            total_images,
            total_annotations,
            total_forms,
            total_tables,
            len(regions),
        ):
            limited = True
            limit_reason = "PDF structural extraction limit reached"
            page_warnings.append(limit_reason)
            break
        table_rects = []
        for table_index, table in enumerate(tables):
            if len(regions) >= policy.max_regions:
                limited = True
                limit_reason = "region limit reached"
                break
            region, profile = _table_region(
                container, page, page_id, page_index + 1, table, table_index
            )
            table_rects.append(fitz.Rect(table.bbox))
            regions.append(region)
            profiles.append((region.region_id, profile))
        for block_index, block in enumerate(text_blocks):
            rect = fitz.Rect(block[:4])
            if any(rect.intersects(table_rect) for table_rect in table_rects):
                continue
            if len(regions) >= policy.max_regions:
                limited = True
                limit_reason = "region limit reached"
                break
            region, profile = _text_region(
                container,
                page_id,
                page_index + 1,
                block_index,
                rect,
                str(block[4]),
                page.rect,
                policy,
            )
            regions.append(region)
            profiles.append((region.region_id, profile))
            normalized = _bounded_normalized_text(str(block[4]), 80)
            at_page_edge = (
                rect.y0 <= page.rect.height * 0.12
                or rect.y1 >= page.rect.height * 0.88
            )
            if normalized and at_page_edge:
                page_edge_text.setdefault(normalized, []).append(page_index + 1)
        if not text_blocks and image_rects:
            page_warnings.append("image-only page; OCR not attempted")
            for image_index, rect in enumerate(image_rects):
                if len(regions) >= policy.max_regions:
                    limited = True
                    limit_reason = "region limit reached"
                    break
                region, profile = _image_region(
                    container,
                    page_id,
                    page_index + 1,
                    image_index,
                    rect,
                )
                regions.append(region)
                profiles.append((region.region_id, profile))
        for widget_index, widget in enumerate(widgets):
            if len(regions) >= policy.max_regions:
                limited = True
                limit_reason = "region limit reached"
                break
            region, profile = _form_region(
                container,
                page_id,
                page_index + 1,
                widget_index,
                widget.rect,
            )
            regions.append(region)
            profiles.append((region.region_id, profile))
        page_region_ids = tuple(item.region_id for item in regions[page_regions_start:])
        pages.append(
            PageObservation(
                page_id,
                page_index + 1,
                round(page.rect.width, 4),
                round(page.rect.height, 4),
                page.rotation,
                bool(text_count),
                text_count,
                len(text_blocks),
                len(tables),
                len(image_rects),
                len(annotations) + len(links),
                len(widgets),
                tuple(page_warnings),
                page_region_ids,
            )
        )
        if limited:
            break
    repeated = tuple(
        text for text, page_numbers in sorted(page_edge_text.items()) if len(set(page_numbers)) > 1
    )
    continuation = _continuation_candidates(regions, profiles)
    state = StructuralState.PARTIAL if limited else StructuralState.DISCOVERED
    warnings = ((limit_reason,) if limit_reason else ())
    resources = ResourceDiagnostics(
        container.size_bytes,
        sheet_or_page_count=len(pages),
        region_count=len(regions),
        extracted_text_size=total_text,
        table_count=total_tables,
        limit_exceeded=limited,
        partial_reason=limit_reason,
    )
    updated = _updated_container(
        container, state, tuple(_dedupe_findings(findings)), resources, warnings
    )
    return PdfDecomposition(
        updated,
        PDF_DECOMPOSITION_VERSION,
        tuple(pages),
        regions=tuple(regions),
        region_profiles=tuple(profiles),
        continuation_candidates=continuation,
        repeated_page_elements=repeated,
        status=state,
        warnings=warnings,
    )


def _find_tables(page):
    try:
        finder = page.find_tables()
        return tuple(finder.tables)
    except (RuntimeError, ValueError, TypeError):
        return ()


def _image_rects(page):
    output = []
    seen = set()
    for image in page.get_images(full=True):
        xref = image[0]
        for rect in page.get_image_rects(xref):
            key = tuple(round(float(value), 4) for value in rect)
            if key not in seen:
                seen.add(key)
                output.append(fitz.Rect(rect))
    return tuple(output)


def _table_region(container, page, page_id, page_number, table, ordinal):
    rect = fitz.Rect(table.bbox)
    extracted = table.extract()
    row_count = int(getattr(table, "row_count", len(extracted)))
    column_count = int(
        getattr(table, "col_count", max((len(row) for row in extracted), default=0))
    )
    headers = tuple(
        str(value).strip()[:80]
        for value in (extracted[0] if extracted else ())
        if value is not None and str(value).strip()
    )[:100]
    location = _location(page_id, page_number, rect, ordinal)
    locator = _pdf_locator(page_number, rect, f"table:{ordinal}")
    profile = PdfRegionProfile(
        1,
        row_count,
        row_count,
        column_count,
        headers,
        (),
        None,
    )
    region = _region(
        container,
        location,
        StructuralType.TABULAR,
        locator,
        0.9 if row_count >= 2 and column_count >= 2 else 0.55,
        profile,
        headers,
    )
    return region, profile


def _text_region(container, page_id, page_number, ordinal, rect, text, page_rect, policy):
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    structural_type, confidence = _classify_text(lines)
    locator = _pdf_locator(page_number, rect, f"block:{ordinal}")
    location = _location(page_id, page_number, rect, ordinal)
    labels = _text_labels(lines, structural_type)
    font_sizes = ()
    profile = PdfRegionProfile(
        1,
        len(lines),
        None,
        None,
        labels,
        font_sizes,
        _bounded_normalized_text(text, policy.max_excerpt_length),
    )
    warnings = ()
    if rect.y0 <= page_rect.height * 0.12 or rect.y1 >= page_rect.height * 0.88:
        warnings = ("page-edge text preserved for repeated header/footer review",)
    region = _region(
        container,
        location,
        structural_type,
        locator,
        confidence,
        profile,
        labels,
        warnings,
    )
    return region, profile


def _image_region(container, page_id, page_number, ordinal, rect):
    locator = _pdf_locator(page_number, rect, f"image:{ordinal}")
    location = _location(page_id, page_number, rect, ordinal)
    profile = PdfRegionProfile(1, 0, None, None, (), (), None, image_count=1)
    return (
        _region(
            container,
            location,
            StructuralType.UNKNOWN,
            locator,
            1.0,
            profile,
            (),
            ("image-only evidence; OCR not attempted",),
            StructuralState.UNRESOLVED,
        ),
        profile,
    )


def _form_region(container, page_id, page_number, ordinal, rect):
    locator = _pdf_locator(page_number, rect, f"form:{ordinal}")
    location = _location(page_id, page_number, rect, ordinal)
    profile = PdfRegionProfile(1, 0, None, None, (), (), None)
    return (
        _region(container, location, StructuralType.FORM, locator, 0.9, profile, ()),
        profile,
    )


def _region(
    container,
    location,
    structural_type,
    locator,
    confidence,
    profile,
    labels,
    warnings=(),
    status=StructuralState.DISCOVERED,
):
    lineage = StructuralLineage(container.source_reference, container.container_id, locator)
    return EvidenceRegion(
        container.context,
        container.container_id,
        None,
        location,
        structural_type,
        locator,
        PDF_DECOMPOSITION_VERSION,
        confidence,
        lineage,
        tuple(labels),
        profile_reference=structural_fingerprint(
            PDF_DECOMPOSITION_VERSION + ".profile", profile
        ),
        warnings=tuple(warnings),
        status=status,
    )


def _classify_text(lines):
    if not lines:
        return StructuralType.UNKNOWN, 0.0
    colon_rows = sum(bool(re.match(r"^.{1,80}:\s*\S+", line)) for line in lines)
    numeric_rows = sum(bool(re.search(r"[-+]?\d[\d,]*(?:\.\d+)?\s*$", line)) for line in lines)
    if len(lines) >= 2 and colon_rows >= max(2, len(lines) - 1):
        return StructuralType.KEY_VALUE, 0.75
    if len(lines) >= 2 and numeric_rows >= max(2, len(lines) - 1):
        return StructuralType.SUMMARY, 0.65
    return StructuralType.TEXT, 0.7


def _text_labels(lines, structural_type):
    if structural_type not in {StructuralType.KEY_VALUE, StructuralType.SUMMARY}:
        return ()
    labels = []
    for line in lines[:100]:
        if ":" in line:
            label = line.split(":", 1)[0]
        else:
            label = re.sub(r"\s+[-+]?\d[\d,]*(?:\.\d+)?\s*$", "", line)
        if label.strip():
            labels.append(label.strip()[:80])
    return tuple(labels)


def _location(page_id, page_number, rect, reading_order):
    return PdfLocation(
        page_id,
        page_number,
        tuple(round(float(value), 4) for value in rect),
        reading_order,
    )


def _pdf_locator(page_number, rect, kind):
    bounds = ",".join(f"{float(value):.4f}" for value in rect)
    return f"page:{page_number}:{kind}:bbox:{bounds}"


def _bounded_normalized_text(text, limit):
    normalized = " ".join(text.split())
    return normalized[:limit] if normalized else ""


def _byte_security_findings(content):
    findings = []
    indicators = (
        (b"/JavaScript", "JavaScript action metadata observed"),
        (b"/JS", "JavaScript action metadata observed"),
        (b"/Launch", "launch action metadata observed"),
        (b"/OpenAction", "document open action metadata observed"),
    )
    for marker, detail in indicators:
        if marker in content:
            findings.append(SecurityDiagnostic(SecurityFinding.ACTIVE_CONTENT_PRESENT, detail))
    return tuple(_dedupe_findings(findings))


def _dangerous(findings):
    return any(
        item.finding
        in {
            SecurityFinding.ACTIVE_CONTENT_PRESENT,
            SecurityFinding.EMBEDDED_OBJECTS_PRESENT,
        }
        for item in findings
    )


def _limits_exceeded(policy, text, blocks, images, annotations, forms, tables, regions):
    return (
        text > policy.max_text_characters
        or blocks > policy.max_text_blocks
        or images > policy.max_images
        or annotations > policy.max_annotations
        or forms > policy.max_forms
        or tables > policy.max_tables
        or regions > policy.max_regions
    )


def _continuation_candidates(regions, profiles):
    by_id = dict(profiles)
    tables = [item for item in regions if item.structural_type is StructuralType.TABULAR]
    output = []
    for left, right in zip(tables, tables[1:]):
        left_profile = by_id[left.region_id]
        right_profile = by_id[right.region_id]
        if (
            right.location.page_number == left.location.page_number + 1
            and left_profile.column_count == right_profile.column_count
        ):
            output.append((left.region_id, right.region_id))
    return tuple(output)


def _dedupe_findings(findings):
    seen = set()
    output = []
    for item in findings:
        key = (item.finding, item.safe_detail)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _container(
    context,
    fingerprint,
    size,
    admitted_at,
    source_reference,
    filename,
    state,
    findings,
    resources,
    warnings,
):
    return UploadContainer(
        context,
        fingerprint,
        "PDF",
        size,
        admitted_at,
        source_reference,
        security_status=state,
        security_diagnostics=findings,
        resource_diagnostics=resources,
        warnings=warnings,
        filename=filename,
    )


def _updated_container(container, state, findings, resources, warnings):
    return _container(
        container.context,
        container.content_fingerprint,
        container.size_bytes,
        container.admitted_at,
        container.source_reference,
        container.filename,
        state,
        findings,
        resources or container.resource_diagnostics,
        warnings,
    )


def _quarantined(container, finding, detail):
    diagnostic = SecurityDiagnostic(finding, detail)
    updated = _updated_container(
        container, StructuralState.QUARANTINED, (diagnostic,), None, (detail,)
    )
    return PdfDecomposition(
        updated,
        PDF_DECOMPOSITION_VERSION,
        (),
        status=StructuralState.QUARANTINED,
        warnings=(detail,),
    )
