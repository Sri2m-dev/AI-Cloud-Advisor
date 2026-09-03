from __future__ import annotations

from universal_evidence.financial.intelligence import analyze_financial_evidence
from universal_evidence.financial.models import EvidenceTable
from universal_evidence.pilot.admission import admitted_source_rows


def table_from_admission(admission) -> EvidenceTable:
    """Adapt the certified structural admission; do not reimplement XLSX parsing."""
    regions = [region for region in admission.regions if region.region_kind == "PRIMARY_DETAIL"]
    if len(regions) != 1:
        raise ValueError("one governed primary detail region is required")
    region = regions[0]
    rows_by_sheet = admitted_source_rows(admission)
    cached_rows_by_sheet = admitted_source_rows(admission, data_only=True)
    sheet_index = next(
        index
        for index, profile in enumerate(admission.profile.sheets)
        if profile.sheet.sheet_id == region.sheet_id
    )
    source_rows = rows_by_sheet[sheet_index]
    cached_source_rows = cached_rows_by_sheet[sheet_index]
    width = len(region.original_headers)
    rows = []
    formula_cells = []
    cached_formula_cells = []
    for row_index, source_row in enumerate(
        source_rows[region.header_row : region.end_row]
    ):
        cached_row = cached_source_rows[region.header_row + row_index]
        values = []
        for column_index in range(width):
            value = source_row[column_index] if column_index < len(source_row) else None
            cached = cached_row[column_index] if column_index < len(cached_row) else None
            if isinstance(value, str) and value.startswith("="):
                formula_cells.append((row_index, column_index))
                if cached is not None:
                    value = cached
                    cached_formula_cells.append((row_index, column_index))
            values.append(value)
        rows.append(tuple(values))
    leading_context = [
        str(value)
        for row in source_rows[: region.header_row - 1]
        for value in row
        if value not in (None, "")
    ]
    scope = admission.scope
    if not scope.organization_id or not scope.tenant_id:
        raise PermissionError("authenticated organization and tenant scope are required")
    return EvidenceTable(
        scope.organization_id,
        scope.tenant_id,
        scope.prospect_id,
        scope.analysis_id,
        admission.source_id,
        admission.file_id,
        region.sheet_id,
        region.sheet_name,
        region.original_headers,
        tuple(rows),
        (("workbook_context", " ".join(leading_context)),),
        tuple(formula_cells),
        tuple(cached_formula_cells),
    )


def analyze_admitted_financial_evidence(admission, **governance):
    """Run CMP-P1 intelligence from the production admission boundary."""
    return analyze_financial_evidence(table_from_admission(admission), **governance)
