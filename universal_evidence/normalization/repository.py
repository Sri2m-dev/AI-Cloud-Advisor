"""Immutable in-memory PUE-004 normalization-run repository."""

from universal_evidence.normalization.models import NormalizationRun


class InMemoryNormalizedEvidenceRepository:
    def __init__(self) -> None:
        self._runs: dict[str, NormalizationRun] = {}
        self._fingerprints: dict[str, str] = {}
        self._versions: dict[tuple[str, ...], list[str]] = {}

    def store_run(self, run: NormalizationRun, version_key: tuple[str, ...]) -> NormalizationRun:
        existing_id = self._fingerprints.get(run.fingerprint)
        if existing_id is not None:
            return self._runs[existing_id]
        self._runs[run.normalization_run_id] = run
        self._fingerprints[run.fingerprint] = run.normalization_run_id
        self._versions.setdefault(version_key, []).append(run.normalization_run_id)
        return run

    def get_by_analysis(self, analysis_id: str) -> tuple[NormalizationRun, ...]:
        return tuple(run for run in self._runs.values() if run.analysis_id == analysis_id)

    def get_by_column(self, column_id: str) -> tuple[NormalizationRun, ...]:
        return tuple(
            run
            for run in self._runs.values()
            if run.records and run.records[0].column_id == column_id
        )

    def get_by_row(self, row_reference: object) -> tuple[object, ...]:
        return tuple(
            record
            for run in self._runs.values()
            for record in run.records
            if record.row_reference == row_reference
        )

    def get_by_mapping_decision(self, decision_id: str) -> tuple[NormalizationRun, ...]:
        return tuple(run for run in self._runs.values() if run.mapping_decision_id == decision_id)

    def get_versions(self, version_key: tuple[str, ...]) -> tuple[NormalizationRun, ...]:
        return tuple(self._runs[run_id] for run_id in self._versions.get(version_key, ()))
