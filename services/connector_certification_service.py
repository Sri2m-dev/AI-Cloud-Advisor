from __future__ import annotations

from uuid import UUID

from core.connectors.certification.certification_check import (
    CertificationCheckStatus,
    CertificationSeverity,
    ConnectorCertificationCheck,
)
from core.connectors.certification.certification_result import (
    ConnectorCertificationResult,
    ConnectorCertificationStatus,
)
from core.connectors.certification.certification_suite import ConnectorCertificationSuite
from core.connectors.certification.health_policy import ConnectorHealthAssessment, ConnectorHealthPolicy
from core.connectors.connector_health import ConnectorHealthStatus
from core.connectors.connector_result import ConnectorRunStatus
from repositories.connector_certification_repository import ConnectorCertificationRepository
from repositories.connector_repository import ConnectorRepository


class ConnectorCertificationService:
    def __init__(
        self,
        connector_repository: ConnectorRepository | None = None,
        certification_repository: ConnectorCertificationRepository | None = None,
        suite: ConnectorCertificationSuite | None = None,
    ):
        self.connector_repository = connector_repository or ConnectorRepository()
        self.certification_repository = certification_repository or ConnectorCertificationRepository()
        self.suite = suite or ConnectorCertificationSuite()

    def certify_connector(self, connector_id: UUID | str) -> ConnectorCertificationResult:
        entry = self.connector_repository.get_connector(connector_id)
        if not entry:
            raise KeyError(f"Connector not found: {connector_id}")

        checks = [
            self._check_enabled(entry.config.enabled),
            self._check_auth(entry.config.auth_type),
            self._check_capabilities(entry.capabilities),
            self._check_fabric_hooks(entry.capabilities),
            self._check_health(entry.connector_id),
            self._check_run_history(entry.connector_id),
        ]
        score = self._score(checks)
        status = self._status(checks)
        result = ConnectorCertificationResult(
            connector_id=entry.connector_id,
            status=status,
            score=score,
            suite_name=self.suite.name,
            checks=checks,
            summary=self._summary(status, score, checks),
            metadata={
                "provider": entry.config.provider,
                "connector_type": entry.config.connector_type,
            },
        )
        return self.certification_repository.save_certification(result)

    def assess_health(
        self,
        connector_id: UUID | str,
        policy: ConnectorHealthPolicy | None = None,
    ) -> ConnectorHealthAssessment:
        resolved_id = UUID(str(connector_id))
        selected_policy = policy or self.certification_repository.default_policy()
        health = self.connector_repository.get_health(resolved_id)
        if not health:
            assessment = ConnectorHealthAssessment(
                connector_id=resolved_id,
                grade=selected_policy.grade_for(0),
                score=0,
                policy_name=selected_policy.name,
                findings=["No connector health result has been published"],
            )
            return self.certification_repository.save_health_assessment(assessment)

        findings = []
        if health.status not in {ConnectorHealthStatus.HEALTHY.value, ConnectorHealthStatus.DEGRADED.value}:
            findings.append(f"Health status is {health.status}")
        if health.error_count > selected_policy.max_error_count:
            findings.append("Error count exceeds health policy")
        if health.latency_ms > selected_policy.max_latency_ms:
            findings.append("Latency exceeds health policy")

        assessment = ConnectorHealthAssessment(
            connector_id=resolved_id,
            grade=selected_policy.grade_for(health.score, health.error_count, health.latency_ms),
            score=health.score,
            policy_name=selected_policy.name,
            findings=findings,
            metadata={"health_status": health.status, "checked_at": health.checked_at},
        )
        return self.certification_repository.save_health_assessment(assessment)

    def certification_summary(self, connector_id: UUID | str) -> dict:
        certification = self.certification_repository.latest_certification(connector_id)
        health = self.certification_repository.latest_health_assessment(connector_id)
        return {
            "certification": certification.to_dict() if certification else None,
            "health_assessment": health.to_dict() if health else None,
        }

    def _check_enabled(self, enabled: bool) -> ConnectorCertificationCheck:
        return ConnectorCertificationCheck(
            name="Connector enabled",
            status=CertificationCheckStatus.PASSED.value if enabled else CertificationCheckStatus.FAILED.value,
            severity=CertificationSeverity.BLOCKER.value,
            message="Connector is enabled." if enabled else "Connector is disabled.",
        )

    def _check_auth(self, auth_type: str) -> ConnectorCertificationCheck:
        passed = bool(auth_type.strip())
        return ConnectorCertificationCheck(
            name="Authentication configured",
            status=CertificationCheckStatus.PASSED.value if passed else CertificationCheckStatus.FAILED.value,
            severity=CertificationSeverity.BLOCKER.value,
            message=f"Authentication type is {auth_type}." if passed else "Authentication type is missing.",
        )

    def _check_capabilities(self, capabilities: list[str]) -> ConnectorCertificationCheck:
        missing = sorted(set(self.suite.required_capabilities) - set(capabilities))
        return ConnectorCertificationCheck(
            name="Lifecycle capability coverage",
            status=CertificationCheckStatus.FAILED.value if missing else CertificationCheckStatus.PASSED.value,
            severity=CertificationSeverity.BLOCKER.value,
            message="All lifecycle capabilities are present." if not missing else f"Missing capabilities: {', '.join(missing)}",
            evidence={"missing": missing, "required": list(self.suite.required_capabilities)},
        )

    def _check_fabric_hooks(self, capabilities: list[str]) -> ConnectorCertificationCheck:
        missing = sorted(set(self.suite.required_fabric_hooks) - set(capabilities))
        return ConnectorCertificationCheck(
            name="Enterprise Data Fabric participation",
            status=CertificationCheckStatus.WARNING.value if missing else CertificationCheckStatus.PASSED.value,
            severity=CertificationSeverity.WARNING.value,
            message="Connector participates in Data Fabric sync flows." if not missing else f"Missing fabric hooks: {', '.join(missing)}",
            evidence={"missing": missing, "required": list(self.suite.required_fabric_hooks)},
        )

    def _check_health(self, connector_id: UUID) -> ConnectorCertificationCheck:
        health = self.connector_repository.get_health(connector_id)
        if not health:
            return ConnectorCertificationCheck(
                name="Health result published",
                status=CertificationCheckStatus.FAILED.value,
                severity=CertificationSeverity.BLOCKER.value,
                message="No health result has been published.",
            )
        passed = health.status in {ConnectorHealthStatus.HEALTHY.value, ConnectorHealthStatus.DEGRADED.value} and health.score >= self.suite.minimum_health_score
        return ConnectorCertificationCheck(
            name="Health policy compliance",
            status=CertificationCheckStatus.PASSED.value if passed else CertificationCheckStatus.FAILED.value,
            severity=CertificationSeverity.BLOCKER.value,
            message=f"Health score is {health.score} with status {health.status}.",
            evidence={"minimum_health_score": self.suite.minimum_health_score},
        )

    def _check_run_history(self, connector_id: UUID) -> ConnectorCertificationCheck:
        results = self.connector_repository.list_results(connector_id)
        successful_operations = {
            result.operation
            for result in results
            if result.status in {ConnectorRunStatus.SUCCESS.value, ConnectorRunStatus.PARTIAL.value}
        }
        missing = sorted(set(self.suite.required_successful_operations) - successful_operations)
        return ConnectorCertificationCheck(
            name="Successful sync run history",
            status=CertificationCheckStatus.WARNING.value if missing else CertificationCheckStatus.PASSED.value,
            severity=CertificationSeverity.WARNING.value,
            message="Required sync operations have successful history." if not missing else f"Missing successful runs: {', '.join(missing)}",
            evidence={"missing": missing, "successful_operations": sorted(successful_operations)},
        )

    @staticmethod
    def _score(checks: list[ConnectorCertificationCheck]) -> float:
        if not checks:
            return 0.0
        points = 0.0
        for check in checks:
            if check.status == CertificationCheckStatus.PASSED.value:
                points += 1.0
            elif check.status == CertificationCheckStatus.WARNING.value:
                points += 0.5
        return round((points / len(checks)) * 100, 2)

    @staticmethod
    def _status(checks: list[ConnectorCertificationCheck]) -> str:
        has_blocker_failure = any(
            check.status == CertificationCheckStatus.FAILED.value
            and check.severity == CertificationSeverity.BLOCKER.value
            for check in checks
        )
        if has_blocker_failure:
            return ConnectorCertificationStatus.FAILED.value
        has_warning = any(check.status == CertificationCheckStatus.WARNING.value for check in checks)
        return ConnectorCertificationStatus.CONDITIONAL.value if has_warning else ConnectorCertificationStatus.CERTIFIED.value

    @staticmethod
    def _summary(status: str, score: float, checks: list[ConnectorCertificationCheck]) -> str:
        failed = [check.name for check in checks if check.status == CertificationCheckStatus.FAILED.value]
        if failed:
            return f"{status} certification with score {score:.1f}. Failed checks: {', '.join(failed)}."
        return f"{status} certification with score {score:.1f}."
