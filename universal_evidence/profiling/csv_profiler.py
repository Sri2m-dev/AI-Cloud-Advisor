"""Bounded standard-library CSV structural profiler."""

from __future__ import annotations

import csv
import io
from dataclasses import replace

from universal_evidence.contracts import EvidenceFile, EvidenceSheet, EvidenceSource
from universal_evidence.profiling.common import (
    build_column_profile,
    detect_header,
    duplicate_header_ordinals,
    exact_duplicate_count,
    nonempty,
    row_regions,
)
from universal_evidence.profiling.models import (
    FileProfile,
    ProfilerConfig,
    ProfileStatus,
    SheetProfile,
    StructuralWarning,
    WarningCode,
)


def _decode(content: bytes) -> tuple[str, str, StructuralWarning | None]:
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16"), "utf-16", None
    try:
        return content.decode("utf-8-sig"), "utf-8-sig", None
    except UnicodeDecodeError:
        text = content.decode("cp1252", errors="replace")
        return (
            text,
            "cp1252",
            StructuralWarning(
                WarningCode.ENCODING_FALLBACK,
                "file",
                "UTF encoding was not valid; deterministic cp1252 fallback used",
            ),
        )


def profile_csv(
    source: EvidenceSource,
    evidence_file: EvidenceFile,
    content: bytes,
    config: ProfilerConfig,
    profiler_version: str,
) -> FileProfile:
    text, encoding, encoding_warning = _decode(content)
    evidence_file = replace(evidence_file, encoding=encoding)
    warnings: list[StructuralWarning] = [encoding_warning] if encoding_warning else []
    sample = text[: min(len(text), 64 * 1024)]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        warnings.append(
            StructuralWarning(
                WarningCode.MALFORMED_RECORDS,
                "file",
                "delimiter could not be confidently detected; comma fallback used",
            )
        )
    malformed = False
    try:
        rows = list(
            csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=True)
        )
    except csv.Error:
        malformed = True
        warnings.append(
            StructuralWarning(
                WarningCode.MALFORMED_RECORDS,
                "file",
                "strict CSV parsing failed; bounded recovery profile produced",
            )
        )
        try:
            rows = list(
                csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=False)
            )
        except csv.Error:
            return FileProfile(
                evidence_file,
                ProfileStatus.MALFORMED,
                "CSV",
                profiler_version,
                source.received_at,
                (),
                encoding,
                getattr(dialect, "delimiter", None),
                getattr(dialect, "quotechar", None),
                warnings=tuple(warnings),
            )

    physical_count = len(rows)
    limited = False
    if len(rows) > config.max_rows_profiled + config.header_scan_rows:
        rows = rows[: config.max_rows_profiled + config.header_scan_rows]
        limited = True
        warnings.append(
            StructuralWarning(
                WarningCode.RESOURCE_LIMIT_REACHED,
                "file",
                "row profiling limit reached",
            )
        )
    width = max((len(row) for row in rows), default=0)
    if width > config.max_columns:
        rows = [row[: config.max_columns] for row in rows]
        width = config.max_columns
        limited = True
        warnings.append(
            StructuralWarning(
                WarningCode.RESOURCE_LIMIT_REACHED,
                "file",
                "column profiling limit reached",
            )
        )
    sheet_id = f"{evidence_file.file_id}:table:1"
    if not rows or not any(any(nonempty(value) for value in row) for row in rows):
        empty_warning = StructuralWarning(
            WarningCode.EMPTY_SHEET, sheet_id, "CSV contains no observable table rows"
        )
        sheet = EvidenceSheet(
            source.context,
            evidence_file.file_id,
            sheet_id,
            "CSV_TABLE",
            1,
            False,
            0,
            0,
            warnings=(empty_warning.code.value,),
        )
        profile = SheetProfile(
            sheet,
            ProfileStatus.PARTIAL,
            None,
            0.0,
            "NO_NONEMPTY_ROWS",
            (),
            0,
            (empty_warning,),
        )
        return FileProfile(
            evidence_file,
            ProfileStatus.PARTIAL,
            "CSV",
            profiler_version,
            source.received_at,
            (profile,),
            encoding,
            dialect.delimiter,
            dialect.quotechar,
            physical_count,
            0,
            tuple(warnings),
        )

    header_row, header_confidence, header_method = detect_header(rows, config)
    sheet_warnings: list[StructuralWarning] = []
    if header_row is None or header_confidence < 0.45:
        sheet_warnings.append(
            StructuralWarning(
                WarningCode.HEADER_UNCERTAIN,
                sheet_id,
                "header candidate has low structural confidence",
            )
        )
    candidate_index = (header_row - 1) if header_row else 0
    headers = list(rows[candidate_index]) + [None] * (
        width - len(rows[candidate_index])
    )
    duplicate_ordinals = duplicate_header_ordinals(headers)
    if duplicate_ordinals:
        sheet_warnings.append(
            StructuralWarning(
                WarningCode.DUPLICATE_HEADERS,
                sheet_id,
                "duplicate header labels observed",
            )
        )
    if any(not nonempty(value) for value in headers):
        sheet_warnings.append(
            StructuralWarning(
                WarningCode.UNNAMED_COLUMNS,
                sheet_id,
                "one or more header cells are blank",
            )
        )
    row_widths = {len(row) for row in rows if any(nonempty(value) for value in row)}
    if len(row_widths) > 1:
        sheet_warnings.append(
            StructuralWarning(
                WarningCode.INCONSISTENT_ROW_WIDTH,
                sheet_id,
                "logical records have inconsistent widths",
            )
        )
    data_rows: list[tuple[int, list[object]]] = []
    repeated = 0
    header_signature = tuple(str(value).strip() for value in headers)
    for row_number, row in enumerate(
        rows[candidate_index + 1 :], start=candidate_index + 2
    ):
        padded = list(row) + [None] * (width - len(row))
        if not any(nonempty(value) for value in padded):
            continue
        if tuple(str(value).strip() for value in padded) == header_signature:
            repeated += 1
            continue
        data_rows.append((row_number, padded))
    if len(data_rows) > config.max_rows_profiled:
        data_rows = data_rows[: config.max_rows_profiled]
        limited = True
        warnings.append(
            StructuralWarning(
                WarningCode.RESOURCE_LIMIT_REACHED,
                "file",
                "logical data row profiling limit reached",
            )
        )
    if repeated:
        sheet_warnings.append(
            StructuralWarning(
                WarningCode.REPEATED_HEADER_ROWS,
                sheet_id,
                f"{repeated} repeated header-like row(s) observed",
            )
        )
    regions = row_regions(rows)
    if len(regions) > 1:
        sheet_warnings.append(
            StructuralWarning(
                WarningCode.MULTIPLE_TABLE_REGIONS,
                sheet_id,
                "multiple non-empty row regions separated by blanks",
            )
        )
    columns = []
    for ordinal in range(width):
        column_id = f"{sheet_id}:column:{ordinal + 1}"
        values = [(row_number, row[ordinal], False) for row_number, row in data_rows]
        columns.append(
            build_column_profile(
                context=source.context,
                file_id=evidence_file.file_id,
                sheet_id=sheet_id,
                column_id=column_id,
                original_header=headers[ordinal],
                ordinal=ordinal + 1,
                values=values,
                config=config,
            )
        )
    duplicate_count = exact_duplicate_count([row for _, row in data_rows])
    partial = malformed or limited or len(regions) > 1 or header_confidence < 0.45
    status = ProfileStatus.PARTIAL if partial else ProfileStatus.COMPLETE
    all_sheet_warnings = tuple(
        sheet_warnings + [warning for column in columns for warning in column.warnings]
    )
    sheet = EvidenceSheet(
        source.context,
        evidence_file.file_id,
        sheet_id,
        "CSV_TABLE",
        1,
        False,
        len(data_rows),
        width,
        header_row,
        candidate_index,
        0,
        False,
        False,
        tuple(warning.code.value for warning in all_sheet_warnings),
    )
    sheet_profile = SheetProfile(
        sheet,
        status,
        (header_row or 1, 1, len(rows), width),
        header_confidence,
        header_method,
        tuple(columns),
        duplicate_count,
        all_sheet_warnings,
    )
    return FileProfile(
        evidence_file,
        status,
        "CSV",
        profiler_version,
        source.received_at,
        (sheet_profile,),
        encoding,
        dialect.delimiter,
        dialect.quotechar,
        physical_count,
        len(data_rows),
        tuple(warnings),
    )
