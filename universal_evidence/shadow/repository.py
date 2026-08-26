"""Disposable, process-local PUE-010 artifact repository."""


class InMemoryShadowRepository:
    def __init__(self) -> None:
        self._analyses = {}
        self._questions = {}
        self._runtimes = {}

    def store_analysis(self, result, runtime):
        existing = self._analyses.get(result.fingerprint)
        if existing is not None:
            return existing
        self._analyses[result.fingerprint] = result
        self._runtimes[result.shadow_run_id] = runtime
        return result

    def store_question(self, result):
        return self._questions.setdefault(result.fingerprint, result)

    def runtime(self, shadow_run_id):
        return self._runtimes.get(shadow_run_id)

    def purge_analysis(self, analysis_id: str) -> int:
        runs = [item for item in self._analyses.values() if item.scope_key[0] == analysis_id]
        run_ids = {item.shadow_run_id for item in runs}
        for item in runs:
            self._analyses.pop(item.fingerprint, None)
            self._runtimes.pop(item.shadow_run_id, None)
        questions = [item for item in self._questions.values() if item.shadow_run_id in run_ids]
        for item in questions:
            self._questions.pop(item.fingerprint, None)
        return len(runs) + len(questions)

    def analysis_available(self, shadow_run_id: str) -> bool:
        return shadow_run_id in self._runtimes
