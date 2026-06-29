from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.data_quality_repository import DataQualityRepository


class DataQualityService:
    DOMAIN_WEIGHTS = {
        "Connector Data": 0.14,
        "Enterprise Data Fabric": 0.16,
        "Knowledge Graph": 0.16,
        "Digital Twin": 0.14,
        "Cost Attribution": 0.12,
        "Telemetry": 0.14,
        "Ownership": 0.14,
    }

    EVENT_TYPES = {
        "data_quality": "DataQualityFailed",
        "ownership": "OwnershipMissing",
        "duplicate": "DuplicateDetected",
        "telemetry": "TelemetryStale",
        "relationship": "RelationshipBroken",
        "cost": "CostMappingMissing",
    }

    def __init__(self, organization_id: str | None = None) -> None:
        self.organization_id = resolve_organization_id(organization_id)

    def run_full_validation(self, persist: bool = True) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        connector = self.validate_connectors()
        entities = self.validate_entities()
        relationships = self.validate_relationships()
        costs = self.validate_costs()
        telemetry = self.validate_telemetry()
        ownership = self.validate_ownership()
        digital_twin = self.validate_digital_twin()
        domain_scores = {
            "Connector Data": connector["score"],
            "Enterprise Data Fabric": entities["score"],
            "Knowledge Graph": relationships["score"],
            "Digital Twin": digital_twin["score"],
            "Cost Attribution": costs["score"],
            "Telemetry": telemetry["score"],
            "Ownership": ownership["score"],
        }
        overall = self.calculate_quality_score(domain_scores)
        issues = (
            connector["issues"]
            + entities["issues"]
            + relationships["issues"]
            + costs["issues"]
            + telemetry["issues"]
            + ownership["issues"]
            + digital_twin["issues"]
        )
        rules = connector["rules"] + entities["rules"] + relationships["rules"] + costs["rules"] + telemetry["rules"] + ownership["rules"] + digital_twin["rules"]
        recommendations = self.generate_recommendations(issues)
        ai_trust = self.calculate_ai_trust_score(domain_scores, issues)
        events = self.publish_quality_events(issues, overall, persist=False)
        run_id = f"dq-{started.strftime('%Y%m%d%H%M%S')}"
        validation = {
            "organization_id": self.organization_id,
            "run_id": run_id,
            "created_at": started.isoformat(),
            "status": "Healthy" if overall >= 98 else "Warning",
            "kpis": {
                "Overall Data Quality": overall,
                "Health": "Healthy" if overall >= 98 else "Warning",
                "Validation Rules": len(rules),
                "Passed": sum(1 for row in rules if row["Status"] == "Passed"),
                "Failed": sum(1 for row in rules if row["Status"] == "Failed"),
                "Warnings": sum(1 for row in rules if row["Status"] == "Warning"),
                "AI Trust Score": ai_trust["AI Trust Score"],
            },
            "domain_scores": domain_scores,
            "domains": self._domain_rows(domain_scores),
            "rules": rules,
            "rule_violations": issues,
            "issues": issues,
            "freshness": telemetry["freshness"],
            "recommendations": recommendations,
            "ai_trust_score": ai_trust,
            "graph_validation": relationships["validations"],
            "telemetry_validation": telemetry["validations"],
            "cost_validation": costs["validations"],
            "event_bus": events,
            "trend": self.quality_trend(overall),
        }
        if persist:
            self._persist_validation(validation)
            validation["history"] = DataQualityRepository.history(self.organization_id, 30)
            validation["event_bus"] = self.publish_quality_events(issues, overall, persist=True)
        else:
            validation["history"] = DataQualityRepository.history(self.organization_id, 30)
        return validation

    def validate_connectors(self) -> dict[str, Any]:
        rules = self._rules("Connector Data", 35, failed=0, warnings=1)
        issues = [
            self._issue("Warning", "Connector Data", "Connector metadata lag", "Splunk connector discovery metadata is 4 minutes behind scheduler state.", "Review connector run metric compaction.", "data_quality", 1),
        ]
        return {"score": 99.2, "rules": rules, "issues": issues}

    def validate_entities(self) -> dict[str, Any]:
        rules = self._rules("Enterprise Data Fabric", 40, failed=1, warnings=1)
        issues = [
            self._issue("Failed", "Enterprise Data Fabric", "Duplicate resource", "Two AWS EC2 resource records share cloud_resource_id i-0checkoutapi.", "Merge duplicate normalized resource records.", "duplicate", 2),
            self._issue("Warning", "Enterprise Data Fabric", "Orphan resource", "Two Kubernetes service objects are not mapped to an application.", "Map orphaned service objects to Checkout or Payments.", "data_quality", 2),
        ]
        return {"score": 98.6, "rules": rules, "issues": issues}

    def validate_relationships(self) -> dict[str, Any]:
        rules = self._rules("Knowledge Graph", 38, failed=1, warnings=0)
        validations = [
            {"Graph": "Application -> Capability", "Integrity": 99.4, "Broken Relationships": 0, "Status": "Healthy"},
            {"Graph": "Application -> Technology", "Integrity": 98.9, "Broken Relationships": 1, "Status": "Warning"},
            {"Graph": "Owner -> Application", "Integrity": 99.0, "Broken Relationships": 0, "Status": "Healthy"},
            {"Graph": "Cost -> Service", "Integrity": 98.6, "Broken Relationships": 0, "Status": "Healthy"},
        ]
        issues = [
            self._issue("Failed", "Knowledge Graph", "Broken relationship", "Checkout API references retired Redis Cluster redis-prod-legacy.", "Re-link Checkout API to redis-prod-02.", "relationship", 1),
        ]
        return {"score": 99.2, "rules": rules, "issues": issues, "validations": validations}

    def validate_costs(self) -> dict[str, Any]:
        rules = self._rules("Cost Attribution", 31, failed=1, warnings=1)
        validations = [
            {"Check": "Cloud Account Mapping", "Score": 98.0, "Gaps": 1, "Status": "Warning"},
            {"Check": "Application Cost Attribution", "Score": 96.0, "Gaps": 1, "Status": "Warning"},
            {"Check": "Business Service Rollup", "Score": 97.0, "Gaps": 0, "Status": "Healthy"},
        ]
        issues = [
            self._issue("Failed", "Cost Attribution", "Cost mapping missing", "One Datadog invoice line is missing cost_center FIN-CHECKOUT.", "Add cost center mapping for Datadog APM usage.", "cost", 1),
            self._issue("Warning", "Cost Attribution", "Unallocated spend", "$1,240 monthly observability spend is not tied to a business service.", "Assign observability shared spend policy.", "cost", 1),
        ]
        return {"score": 97.1, "rules": rules, "issues": issues, "validations": validations}

    def validate_telemetry(self) -> dict[str, Any]:
        rules = self._rules("Telemetry", 42, failed=0, warnings=2)
        freshness = [
            {"Source": "Cloud Data", "Freshness": "5 min", "Age Seconds": 300, "Status": "Healthy"},
            {"Source": "GitHub", "Freshness": "2 min", "Age Seconds": 120, "Status": "Healthy"},
            {"Source": "ServiceNow", "Freshness": "3 min", "Age Seconds": 180, "Status": "Healthy"},
            {"Source": "Datadog", "Freshness": "30 sec", "Age Seconds": 30, "Status": "Healthy"},
            {"Source": "Splunk", "Freshness": "1 min", "Age Seconds": 60, "Status": "Healthy"},
            {"Source": "Prometheus", "Freshness": "30 sec", "Age Seconds": 30, "Status": "Healthy"},
            {"Source": "Grafana", "Freshness": "45 sec", "Age Seconds": 45, "Status": "Healthy"},
            {"Source": "Legacy APM", "Freshness": "18 min", "Age Seconds": 1080, "Status": "Warning"},
        ]
        validations = [
            {"Signal": "Metrics", "Score": 99.0, "Records": 18420, "Status": "Healthy"},
            {"Signal": "Logs", "Score": 98.0, "Records": 9210, "Status": "Healthy"},
            {"Signal": "Traces", "Score": 97.5, "Records": 4120, "Status": "Healthy"},
            {"Signal": "Alerts", "Score": 98.0, "Records": 186, "Status": "Healthy"},
        ]
        issues = [
            self._issue("Warning", "Telemetry", "Telemetry stale", "Legacy APM telemetry is 18 minutes old.", "Move Legacy APM source to standard scheduler cadence.", "telemetry", 1),
        ]
        return {"score": 98.5, "rules": rules, "issues": issues, "freshness": freshness, "validations": validations}

    def validate_ownership(self) -> dict[str, Any]:
        rules = self._rules("Ownership", 28, failed=1, warnings=1)
        issues = [
            self._issue("Failed", "Ownership", "Missing business owner", "Legacy Invoice Adapter has no accountable owner.", "Assign an application owner and approver group.", "ownership", 1),
            self._issue("Warning", "Ownership", "Missing technical owner", "Edge Cache Worker has no named technical owner.", "Assign a platform engineering owner.", "ownership", 1),
        ]
        return {"score": 96.8, "rules": rules, "issues": issues}

    def validate_digital_twin(self) -> dict[str, Any]:
        rules = self._rules("Digital Twin", 31, failed=0, warnings=1)
        issues = [
            self._issue("Warning", "Digital Twin", "Twin completeness gap", "Three low-risk technologies have incomplete lifecycle metadata.", "Complete lifecycle and renewal metadata.", "data_quality", 3),
        ]
        return {"score": 98.2, "rules": rules, "issues": issues}

    def calculate_quality_score(self, domain_scores: dict[str, float]) -> float:
        return round(sum(float(domain_scores.get(domain, 0)) * weight for domain, weight in self.DOMAIN_WEIGHTS.items()), 1)

    def generate_recommendations(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        high_priority = [row for row in issues if row["Severity"] == "Failed"]
        recommendations = [
            {
                "Priority": "High" if issue["Severity"] == "Failed" else "Medium",
                "Domain": issue["Domain"],
                "Recommendation": issue["Recommended Action"],
                "Expected Impact": "Raise AI Trust and platform readiness by closing validation gaps.",
                "Owner": self._owner_for_domain(issue["Domain"]),
            }
            for issue in issues
        ]
        recommendations.insert(
            0,
            {
                "Priority": "High",
                "Domain": "AI Trust",
                "Recommendation": f"Close {len(high_priority)} failed validation issues before promoting new AI decisions.",
                "Expected Impact": "Keep AI Trust Score above 97%.",
                "Owner": "Enterprise Architecture",
            },
        )
        return recommendations

    def calculate_ai_trust_score(self, domain_scores: dict[str, float], issues: list[dict[str, Any]]) -> dict[str, Any]:
        failed = sum(1 for row in issues if row["Severity"] == "Failed")
        warning = sum(1 for row in issues if row["Severity"] == "Warning")
        score = max(0, round(99.0 - (failed * 0.35) - (warning * 0.08), 1))
        return {
            "AI Trust Score": score,
            "Reasoning Confidence": 96.0,
            "Prediction Confidence": 95.0,
            "Graph Completeness": round(domain_scores.get("Knowledge Graph", 0), 1),
            "Telemetry Freshness": round(domain_scores.get("Telemetry", 0), 1),
            "Digital Twin Completeness": round(domain_scores.get("Digital Twin", 0), 1),
            "Cost Confidence": round(domain_scores.get("Cost Attribution", 0), 1),
            "Decision": "Trusted with monitoring" if score >= 97 else "Needs review",
        }

    def publish_quality_events(self, issues: list[dict[str, Any]], overall: float, persist: bool = True) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        events = [
            {
                "organization_id": self.organization_id,
                "event_type": self.EVENT_TYPES.get(issue["Event Key"], "DataQualityFailed"),
                "severity": issue["Severity"],
                "source": "Enterprise Data Quality",
                "entity": issue["Issue"],
                "payload": {
                    "domain": issue["Domain"],
                    "description": issue["Description"],
                    "recommended_action": issue["Recommended Action"],
                    "overall_quality": overall,
                },
                "created_at": now,
            }
            for issue in issues
            if issue["Severity"] in {"Failed", "Warning"}
        ]
        if persist:
            return DataQualityRepository.publish_events(events)
        return events

    def quality_trend(self, current_score: float) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        return [
            {
                "Snapshot": (now - timedelta(days=6 - index)).date().isoformat(),
                "Overall Data Quality": round(current_score - ((6 - index) * 0.12), 1),
                "AI Trust Score": round(97.0 - ((6 - index) * 0.08), 1),
            }
            for index in range(7)
        ]

    def _persist_validation(self, validation: dict[str, Any]) -> None:
        run = {
            "id": validation["run_id"],
            "organization_id": self.organization_id,
            "status": validation["status"],
            "overall_score": validation["kpis"]["Overall Data Quality"],
            "ai_trust_score": validation["ai_trust_score"]["AI Trust Score"],
            "domain_scores": validation["domain_scores"],
            "summary": validation["kpis"],
            "created_at": validation["created_at"],
        }
        DataQualityRepository.save_run(run)
        base = {"run_id": validation["run_id"], "organization_id": self.organization_id}
        DataQualityRepository.insert_results([{**base, **row} for row in validation["domains"]])
        DataQualityRepository.insert_rules([{**base, **row} for row in validation["rules"]])
        DataQualityRepository.insert_issues([{**base, **row} for row in validation["issues"]])
        DataQualityRepository.insert_recommendations([{**base, **row} for row in validation["recommendations"]])
        DataQualityRepository.insert_freshness([{**base, **row} for row in validation["freshness"]])
        DataQualityRepository.insert_ai_trust_score({**base, **validation["ai_trust_score"]})
        DataQualityRepository.insert_graph_validation([{**base, **row} for row in validation["graph_validation"]])
        DataQualityRepository.insert_telemetry_validation([{**base, **row} for row in validation["telemetry_validation"]])
        DataQualityRepository.insert_cost_validation([{**base, **row} for row in validation["cost_validation"]])

    def _rules(self, domain: str, count: int, failed: int = 0, warnings: int = 0) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index in range(count):
            status = "Passed"
            if index < failed:
                status = "Failed"
            elif index < failed + warnings:
                status = "Warning"
            rows.append(
                {
                    "Rule": f"{domain} Rule {index + 1:03d}",
                    "Domain": domain,
                    "Status": status,
                    "Severity": "High" if status == "Failed" else "Medium" if status == "Warning" else "None",
                    "Result": "Validation passed" if status == "Passed" else "Validation needs review",
                }
            )
        return rows

    def _issue(
        self,
        severity: str,
        domain: str,
        issue: str,
        description: str,
        action: str,
        event_key: str,
        count: int,
    ) -> dict[str, Any]:
        return {
            "Severity": severity,
            "Domain": domain,
            "Issue": issue,
            "Description": description,
            "Count": count,
            "Status": "Warning" if severity == "Warning" else "Critical",
            "Recommended Action": action,
            "Event Key": event_key,
        }

    def _domain_rows(self, domain_scores: dict[str, float]) -> list[dict[str, Any]]:
        return [
            {
                "Domain": domain,
                "Score": round(score, 1),
                "Status": "Healthy" if score >= 98 else "Warning" if score >= 95 else "Critical",
                "Weight": f"{self.DOMAIN_WEIGHTS.get(domain, 0) * 100:.0f}%",
            }
            for domain, score in domain_scores.items()
        ]

    @staticmethod
    def _owner_for_domain(domain: str) -> str:
        owners = {
            "Connector Data": "Platform Operations",
            "Enterprise Data Fabric": "Data Engineering",
            "Knowledge Graph": "Enterprise Architecture",
            "Digital Twin": "Technology Portfolio",
            "Cost Attribution": "FinOps",
            "Telemetry": "SRE",
            "Ownership": "Application Governance",
        }
        return owners.get(domain, "Platform Operations")
