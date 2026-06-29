from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from connectors.base.normalizer import ConnectorNormalizer
from connectors.connector_registry import get_connector


CORE_CONNECTORS = [
    "AWS",
    "Azure",
    "GCP",
    "Microsoft 365",
    "ServiceNow",
    "GitHub",
    "Jira",
    "Datadog",
    "Dynatrace",
    "New Relic",
    "Splunk",
    "Prometheus",
    "Grafana",
]

SECRET_SENTINELS = [
    "demo-secret-value",
    "demo-token-value",
    "demo-password-value",
    "demo-private-key-value",
]


@dataclass
class CertificationCheck:
    name: str
    passed: bool
    score: float
    details: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class ConnectorCertificationResult:
    connector: str
    passed: bool
    certification_level: str
    health_score: float
    coverage_percent: float
    duration_ms: float
    checks: list[CertificationCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "connector": self.connector,
            "passed": self.passed,
            "certification_level": self.certification_level,
            "health_score": self.health_score,
            "coverage_percent": self.coverage_percent,
            "duration_ms": self.duration_ms,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "score": check.score,
                    "details": check.details,
                    "error": check.error,
                }
                for check in self.checks
            ],
        }


class ConnectorCertificationRunner:
    def __init__(
        self,
        connectors: list[str] | None = None,
        organization_id: str = "certification-demo-org",
        min_health: int = 96,
        max_latency_ms: float = 750.0,
    ) -> None:
        self.connectors = connectors or CORE_CONNECTORS
        self.organization_id = organization_id
        self.min_health = min_health
        self.max_latency_ms = max_latency_ms

    def run_all(self) -> dict[str, Any]:
        started = perf_counter()
        results = [self.run_connector(name) for name in self.connectors]
        passed = [row for row in results if row.passed]
        return {
            "suite": "Nexora Connector Certification Suite",
            "status": "PASSED" if len(passed) == len(results) else "FAILED",
            "connectors_tested": len(results),
            "connectors_passed": len(passed),
            "connectors_failed": len(results) - len(passed),
            "gold_certified": sum(1 for row in results if row.certification_level == "Gold"),
            "average_health": round(sum(row.health_score for row in results) / len(results), 1) if results else 0,
            "average_coverage": round(sum(row.coverage_percent for row in results) / len(results), 1) if results else 0,
            "duration_ms": round((perf_counter() - started) * 1000, 1),
            "results": [row.as_dict() for row in results],
        }

    def run_connector(self, connector_name: str) -> ConnectorCertificationResult:
        started = perf_counter()
        checks: list[CertificationCheck] = []
        certification: dict[str, Any] = {}
        try:
            connector = get_connector(
                connector_name,
                credentials=self._demo_credentials(connector_name),
                org_id=self.organization_id,
            )
            checks.append(self._authentication_test(connector))
            checks.append(self._sync_test(connector))
            checks.append(self._normalization_test(connector))
            checks.append(self._health_test(connector))
            checks.append(self._security_test(connector))
            checks.append(self._performance_test(connector))
            certification = connector.certification_metadata() if hasattr(connector, "certification_metadata") else {}
            checks.append(self._gold_certification_test(certification))
        except Exception as exc:
            checks.append(CertificationCheck("runner", False, 0, error=str(exc)))
        duration_ms = round((perf_counter() - started) * 1000, 1)
        health_score = float(certification.get("health_score") or 0)
        coverage_percent = self._coverage_percent(certification.get("coverage") or {})
        return ConnectorCertificationResult(
            connector=connector_name,
            passed=all(check.passed for check in checks),
            certification_level=str(certification.get("certification_level") or "Uncertified"),
            health_score=health_score,
            coverage_percent=coverage_percent,
            duration_ms=duration_ms,
            checks=checks,
        )

    def _authentication_test(self, connector: Any) -> CertificationCheck:
        if not hasattr(connector, "authenticate"):
            return CertificationCheck("authentication", False, 0, error="Connector does not implement authenticate().")
        try:
            result = connector.authenticate()
            status = str(result.get("status") or "").upper()
            passed = status in {"AUTHENTICATED", "VALID", "CONNECTED"}
            return CertificationCheck("authentication", passed, 100 if passed else 0, {"status": result.get("status")})
        except Exception as exc:
            return CertificationCheck("authentication", False, 0, error=str(exc))

    def _sync_test(self, connector: Any) -> CertificationCheck:
        if not hasattr(connector, "sync"):
            return CertificationCheck("sync", False, 0, error="Connector does not implement sync().")
        try:
            result = connector.sync()
            objects = int(result.get("objects_synced") or 0)
            tables = result.get("tables_populated") or []
            sources = result.get("sources") or []
            passed = objects > 0 and bool(tables) and bool(sources)
            score = 100 if passed else 40 if objects > 0 else 0
            return CertificationCheck("sync", passed, score, {"objects_synced": objects, "tables": len(tables), "sources": len(sources)})
        except Exception as exc:
            return CertificationCheck("sync", False, 0, error=str(exc))

    def _normalization_test(self, connector: Any) -> CertificationCheck:
        try:
            if hasattr(connector, "normalize"):
                normalized = connector.normalize()
            elif hasattr(connector, "normalize_telemetry"):
                normalized = connector.normalize_telemetry()
            else:
                records = connector.discover() if hasattr(connector, "discover") else []
                normalized = ConnectorNormalizer.normalize_records(connector.connector_name, records)
            quality_scores = [float(row.get("quality_score") or 0) for row in normalized]
            average_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0
            passed = bool(normalized) and average_quality >= 90
            return CertificationCheck("normalization", passed, average_quality, {"records": len(normalized), "average_quality": average_quality})
        except Exception as exc:
            return CertificationCheck("normalization", False, 0, error=str(exc))

    def _health_test(self, connector: Any) -> CertificationCheck:
        try:
            health = connector.health() if hasattr(connector, "health") else connector.certification_metadata()
            score = float(health.get("health_score") or 0)
            passed = score >= self.min_health and str(health.get("status") or "").lower() in {"healthy", "connected", "valid"}
            return CertificationCheck("health", passed, score, {"health_score": score, "status": health.get("status")})
        except Exception as exc:
            return CertificationCheck("health", False, 0, error=str(exc))

    def _security_test(self, connector: Any) -> CertificationCheck:
        try:
            payloads = []
            if hasattr(connector, "authenticate"):
                payloads.append(connector.authenticate())
            if hasattr(connector, "validate_connection"):
                payloads.append(connector.validate_connection())
            if hasattr(connector, "certification_metadata"):
                payloads.append(connector.certification_metadata())
            serialized = json.dumps(payloads, default=str).lower()
            leaked = [secret for secret in SECRET_SENTINELS if secret.lower() in serialized]
            auth_text = getattr(connector, "authentication_type", "")
            has_auth_metadata = bool(auth_text)
            passed = not leaked and has_auth_metadata
            return CertificationCheck("security", passed, 100 if passed else 0, {"secret_leaks": leaked, "authentication": auth_text})
        except Exception as exc:
            return CertificationCheck("security", False, 0, error=str(exc))

    def _performance_test(self, connector: Any) -> CertificationCheck:
        try:
            started = perf_counter()
            connector.sync()
            latency_ms = round((perf_counter() - started) * 1000, 1)
            passed = latency_ms <= self.max_latency_ms
            score = round(max(0, min(100, 100 - (latency_ms / max(self.max_latency_ms, 1) * 20))), 1)
            return CertificationCheck("performance", passed, score, {"latency_ms": latency_ms, "threshold_ms": self.max_latency_ms})
        except Exception as exc:
            return CertificationCheck("performance", False, 0, error=str(exc))

    def _gold_certification_test(self, certification: dict[str, Any]) -> CertificationCheck:
        coverage = certification.get("coverage") or {}
        coverage_percent = self._coverage_percent(coverage)
        health_score = float(certification.get("health_score") or 0)
        level = certification.get("certification_level")
        passed = level == "Gold" and coverage_percent == 100 and health_score >= self.min_health
        return CertificationCheck(
            "gold_certification",
            passed,
            min(coverage_percent, health_score),
            {"level": level, "coverage_percent": coverage_percent, "health_score": health_score},
        )

    def _coverage_percent(self, coverage: dict[str, Any]) -> float:
        if not coverage:
            return 0.0
        complete = sum(1 for value in coverage.values() if bool(value))
        return round(complete / len(coverage) * 100, 1)

    def _demo_credentials(self, connector_name: str) -> dict[str, str]:
        safe_name = connector_name.lower().replace(" ", "_")
        return {
            "client_id": f"{safe_name}-cert-client",
            "api_key": SECRET_SENTINELS[0],
            "token": SECRET_SENTINELS[1],
            "password": SECRET_SENTINELS[2],
            "private_key": SECRET_SENTINELS[3],
        }


def _print_summary(report: dict[str, Any]) -> None:
    print(f"{report['suite']}: {report['status']}")
    print(
        f"Connectors: {report['connectors_passed']}/{report['connectors_tested']} passed | "
        f"Gold: {report['gold_certified']} | Avg health: {report['average_health']} | "
        f"Avg coverage: {report['average_coverage']}%"
    )
    for row in report["results"]:
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"{status} {row['connector']}: {row['certification_level']} | "
            f"health {row['health_score']} | coverage {row['coverage_percent']}% | {row['duration_ms']} ms"
        )
        for check in row["checks"]:
            if not check["passed"]:
                print(f"  - {check['name']} failed: {check['error'] or check['details']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Nexora connector Gold certification checks.")
    parser.add_argument("--connector", action="append", help="Connector name to test. Repeat for multiple connectors.")
    parser.add_argument("--org-id", default="certification-demo-org", help="Organization id used for scoped connector tests.")
    parser.add_argument("--min-health", type=int, default=96, help="Minimum connector health score for Gold certification.")
    parser.add_argument("--max-latency-ms", type=float, default=750.0, help="Maximum sync latency allowed for adapter-mode performance checks.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)

    runner = ConnectorCertificationRunner(
        connectors=args.connector or CORE_CONNECTORS,
        organization_id=args.org_id,
        min_health=args.min_health,
        max_latency_ms=args.max_latency_ms,
    )
    report = runner.run_all()
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_summary(report)
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
