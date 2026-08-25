"""Explicit bytes-oriented PUE-001 profiling boundary."""

from __future__ import annotations

import hashlib
from pathlib import PurePath

from universal_evidence.contracts import EvidenceFile, EvidenceSource
from universal_evidence.profiling.csv_profiler import profile_csv
from universal_evidence.profiling.models import (
    FileProfile,
    ProfilerConfig,
    ProfileStatus,
    StructuralWarning,
    WarningCode,
)
from universal_evidence.profiling.xlsx_profiler import profile_xlsx

PROFILER_VERSION = "pue-001.1"


def profile_evidence(
    *,
    source: EvidenceSource,
    filename: str,
    content: bytes,
    config: ProfilerConfig | None = None,
) -> FileProfile:
    """Profile authorized in-memory evidence without changing source or application state."""
    policy = config or ProfilerConfig()
    suffix = PurePath(filename).suffix.casefold()
    content_hash = hashlib.sha256(content).hexdigest()
    file_id = f"{source.context.source_id}:file:{content_hash[:16]}"
    source_type = suffix.removeprefix(".").upper() or "UNKNOWN"
    mime = (
        "text/csv"
        if suffix == ".csv"
        else (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if suffix == ".xlsx"
            else None
        )
    )
    evidence_file = EvidenceFile(
        source.context,
        file_id,
        filename,
        content_hash,
        source_type,
        len(content),
        mime,
    )
    if len(content) > policy.max_file_size:
        warning = StructuralWarning(
            WarningCode.RESOURCE_LIMIT_REACHED,
            file_id,
            "file size profiling limit reached",
        )
        return FileProfile(
            evidence_file,
            ProfileStatus.PARTIAL,
            source_type,
            PROFILER_VERSION,
            source.received_at,
            (),
            warnings=(warning,),
        )
    if suffix == ".csv":
        return profile_csv(source, evidence_file, content, policy, PROFILER_VERSION)
    if suffix == ".xlsx":
        return profile_xlsx(source, evidence_file, content, policy, PROFILER_VERSION)
    return FileProfile(
        evidence_file,
        ProfileStatus.UNSUPPORTED_FORMAT,
        source_type,
        PROFILER_VERSION,
        source.received_at,
        (),
        warnings=(
            StructuralWarning(
                WarningCode.UNSUPPORTED_CELL_TYPE,
                file_id,
                "format is not supported by PUE-001",
            ),
        ),
    )
