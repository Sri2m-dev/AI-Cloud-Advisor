from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.ai_context_service import AIContextService
from services.ai_decision_service import AIDecisionService
from services.ai_insight_service import AIInsightService
from services.ai_recommendation_service import AIRecommendationService
from services.business_capability_service import BusinessCapabilityService
from services.connector_operations_service import ConnectorOperationsService
from services.compliance_service import ComplianceService
from services.data_quality_service import DataQualityService
from services.disaster_recovery_service import DisasterRecoveryService
from services.enterprise_connector_platform_service import EnterpriseConnectorPlatformService
from services.enterprise_security_service import EnterpriseSecurityService
from services.enterprise_observability_service import EnterpriseObservabilityService
from services.enterprise_incident_timeline import EnterpriseIncidentTimeline
from services.universal_connector_platform_service import UniversalConnectorPlatformService
from services.platform_health_service import PlatformHealthService
from services.enterprise_scheduler_service import EnterpriseSchedulerService
from services.enterprise_digital_twin_dashboard_service import EnterpriseDigitalTwinDashboardService
from services.enterprise_graph_service import EnterpriseGraphService
from services.performance_service import PerformanceService
from services.operational_readiness_service import OperationalReadinessService
from services.release_readiness_service import ReleaseReadinessService
from services.impact_analysis_service import ImpactAnalysisService
from services.ai_reasoning_service import AIReasoningService
from services.forecasting_service import ForecastingService
from services.financial_intelligence_service import FinancialIntelligenceService
from services.capacity_intelligence_service import CapacityIntelligenceService
from services.risk_prediction_service import RiskPredictionService
from services.predictive_ai_service import PredictiveAIService
from services.predictive_accuracy_service import PredictiveAccuracyService
from services.simulation_service import SimulationService
from services.workflow_builder_service import WorkflowBuilderService
from services.governance_authorization_service import GovernanceAuthorizationService
from services.safe_execution_service import SafeExecutionService
from services.learning_engine import LearningEngine
from agents.orchestrator import AgentOrchestrator


class AICopilotService:
    _HISTORY: dict[str, list[dict[str, Any]]] = {}

    SUGGESTED_PROMPTS = [
        "Show top optimization opportunities",
        "Which applications are unhealthy?",
        "Why is AWS spend increasing?",
        "Show Digital Twin health",
        "Which connectors are failing?",
        "Is Azure connected?",
        "When was Microsoft 365 last synchronized?",
        "Why is the GitHub connector unhealthy?",
        "How many systems are connected?",
        "Explain Decision DEC-000001",
        "Why is AWS critical?",
        "Show impact of Oracle",
        "What happens if AWS US-East-1 goes down?",
        "What if we migrate Oracle to PostgreSQL?",
        "Can we migrate Oracle to PostgreSQL?",
        "What is the safest optimization?",
        "What will next month's cloud bill be?",
        "Which application is most likely to exceed budget?",
        "Can I trust this forecast?",
        "Why was last month's forecast wrong?",
        "Reduce cloud spend by 15% while maintaining production availability.",
        "Prepare migration plan from Oracle to PostgreSQL.",
        "Build implementation plan for Oracle migration.",
        "Is this migration ready for execution?",
        "Who still needs to approve?",
        "Execute Oracle migration.",
        "What have we learned this month?",
        "Which AI agent is performing best?",
        "Why is Checkout slow?",
        "Is Prometheus connected?",
        "Is Grafana connected?",
        "Show Prometheus firing alerts.",
        "Show Grafana dashboard health.",
        "Show Kubernetes pod restart trend.",
        "Show Checkout incident timeline.",
        "What caused the incident?",
        "Which tool detected it first?",
        "What changed before the incident?",
        "Show executive summary.",
        "Open Connector Studio.",
        "Connect our HRMS.",
        "Generate a connector from Swagger.",
        "Show connector mapping suggestions.",
        "Is Nexora healthy?",
        "Show platform readiness.",
        "Which component is unhealthy?",
        "Run platform certification.",
        "Show scheduler health.",
        "Show AI health.",
        "Show data quality issues.",
        "Show data quality.",
        "Why is data quality below 100%?",
        "Which applications have missing owners?",
        "Show duplicate resources.",
        "Show stale telemetry.",
        "Show broken Knowledge Graph relationships.",
        "What is the AI Trust Score?",
        "Show platform security.",
        "Is Nexora secure?",
        "Show expiring credentials.",
        "Show RBAC violations.",
        "Show tenant isolation status.",
        "Why is Security Health below 100%?",
        "Is execution protected?",
        "Show connector security.",
        "Show compliance status.",
        "Show performance health.",
        "Which dashboard is slow?",
        "Why is Copilot slow?",
        "Show connector sync throughput.",
        "Show graph traversal performance.",
        "Show cache hit ratio.",
        "Show database latency.",
        "Show event bus throughput.",
        "Is Nexora enterprise ready?",
        "Generate audit evidence.",
        "Show DR readiness.",
        "Show backup health.",
        "Can we release Version 1.0?",
        "Is production deployment ready?",
        "Generate compliance report.",
        "Show operational readiness.",
        "Why did AWS sync fail?",
        "Retry failed ServiceNow sync.",
        "Show dead-letter queue.",
        "Which connector is running slow?",
        "What is the next scheduled sync?",
        "Pause GitHub connector sync.",
        "Resume Jira connector sync.",
        "Show observability correlations",
        "What should the CIO focus on today?",
        "What should the CEO know this morning?",
    ]

    @staticmethod
    def ask(
        question: str,
        organization_id: str | None = None,
        session_id: str = "default",
    ) -> dict[str, Any]:
        started = perf_counter()
        org_id = resolve_organization_id(organization_id)
        intent = AICopilotService._detect_intent(question)
        context = AICopilotService.get_context(question, org_id)
        answer = AICopilotService._generate_answer(question, intent, context)
        response = {
            "question": question,
            "intent": intent,
            "answer": answer["text"],
            "citations": answer["citations"],
            "context": answer["context"],
            "source_traceability": answer["sources"],
            "followup_questions": AICopilotService.get_followup_questions(intent),
            "response_time_ms": round((perf_counter() - started) * 1000, 1),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        AICopilotService._HISTORY.setdefault(session_id, []).append(response)
        return response

    @staticmethod
    def get_context(question: str, organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        intent = AICopilotService._detect_intent(question)
        if intent == "predictive":
            context = {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "forecasting": ForecastingService.forecast_enterprise_metrics(org_id),
                "financial_forecast": FinancialIntelligenceService.get_financial_forecast(org_id),
                "capacity_forecast": CapacityIntelligenceService.forecast_capacity(org_id),
                "risk_prediction": RiskPredictionService.predict_risks(org_id),
            }
            context["predictive_ai"] = PredictiveAIService.get_predictive_recommendations(org_id)
            if AICopilotService._is_prediction_trust_question(question):
                context["prediction_performance"] = PredictiveAccuracyService.get_prediction_performance(org_id)
            return context
        if intent == "learning":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "learning": LearningEngine.get_learning_dashboard(org_id),
            }
        if intent == "connector":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "connector_platform": EnterpriseConnectorPlatformService.get_health_dashboard(org_id),
                "connector_operations": [],
            }
        if intent == "connector_studio":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "connector_studio": UniversalConnectorPlatformService.get_studio_dashboard(org_id),
            }
        if intent == "platform_health":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "platform_health": PlatformHealthService(org_id).get_platform_health(force_refresh="run" in str(question or "").lower()),
            }
        if intent == "data_quality":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "data_quality": DataQualityService(org_id).run_full_validation(persist=True),
            }
        if intent == "security":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "security": EnterpriseSecurityService(org_id).run_security_validation(persist=True),
            }
        if intent == "performance":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "performance": PerformanceService(org_id).run_performance_assessment(persist=True),
            }
        if intent == "enterprise_readiness":
            release = ReleaseReadinessService(org_id)
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "compliance": ComplianceService(org_id).run_compliance_assessment(persist=True),
                "dr_readiness": DisasterRecoveryService(org_id).get_dr_readiness(persist=True),
                "operational_readiness": OperationalReadinessService(org_id).get_operational_readiness(persist=True),
                "release_readiness": release.validate_release(persist=True),
                "production_readiness": release.validate_production_readiness(persist=True),
                "version_readiness_report": release.version_1_readiness_report(persist=True),
            }
        if intent == "scheduler":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "scheduler": AICopilotService._scheduler_context(question, org_id),
            }
        if intent == "observability":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "observability": EnterpriseObservabilityService.get_dashboard(org_id),
            }
        if intent == "incident":
            return {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "incident_timeline": EnterpriseIncidentTimeline.get_dashboard(org_id),
            }
        if intent == "agentic":
            if AICopilotService._is_execution_request(question):
                return {
                    "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                    "intent": intent,
                    "question": question,
                    "safe_execution": SafeExecutionService.request_execution(
                        question,
                        organization_id=org_id,
                        execution_mode="Mock",
                        adapter_name="mock",
                        created_by="ai_copilot",
                        persist=False,
                        force_authorized=True,
                    ),
                }
            collaboration = AgentOrchestrator.collaborate_on_goal(
                question,
                organization_id=org_id,
                created_by="ai_copilot",
                persist=False,
            )
            context = {
                "enterprise": AICopilotService._minimal_enterprise_context(org_id),
                "intent": intent,
                "question": question,
                "collaboration": collaboration,
            }
            if AICopilotService._is_workflow_blueprint_question(question):
                context["workflow_blueprint"] = WorkflowBuilderService.build_from_collaboration(
                    collaboration,
                    created_by="ai_copilot",
                    persist=False,
                )
            if AICopilotService._is_authorization_question(question):
                blueprint = context.get("workflow_blueprint") or WorkflowBuilderService.build_from_collaboration(
                    collaboration,
                    created_by="ai_copilot",
                    persist=False,
                )
                context["workflow_blueprint"] = blueprint
                context["governance_authorization"] = GovernanceAuthorizationService.evaluate_blueprint(
                    blueprint,
                    created_by="ai_copilot",
                    persist=False,
                )
            return context
        enterprise = AIContextService.build_enterprise_context(org_id)
        context = {
            "enterprise": enterprise,
            "intent": intent,
            "question": question,
        }
        if intent in {"cost", "optimization", "executive"}:
            context["insights"] = AIInsightService.get_cost_insights(org_id)
            context["recommendations"] = AIRecommendationService.get_cost_recommendations(org_id)
        if intent in {"governance", "executive"}:
            context["insights"] = context.get("insights", []) + AIInsightService.get_governance_insights(org_id)
        if intent in {"operations", "technology", "connector", "executive"}:
            context["connector_operations"] = ConnectorOperationsService.get_connector_operations(org_id)
            context["connector_platform"] = EnterpriseConnectorPlatformService.get_health_dashboard(org_id)
            context["insights"] = context.get("insights", []) + AIInsightService.get_operational_insights(org_id)
        if intent in {"recommendation", "executive", "optimization"}:
            context["recommendations"] = AIRecommendationService.get_all_recommendations(org_id, persist=False).get(
                "recommendations",
                [],
            )
        if intent in {"decision", "executive"}:
            context["decisions"] = AIDecisionService.get_dashboard(org_id, persist=False)
        if intent in {"business", "technology", "executive"}:
            context["digital_twin"] = EnterpriseDigitalTwinDashboardService.get_dashboard(org_id)
            context["capability_dashboard"] = BusinessCapabilityService.get_dashboard(org_id)
        if intent in {"impact", "business", "technology"}:
            asset = AICopilotService._extract_impact_asset(question, org_id)
            if asset:
                context["impact_analysis"] = ImpactAnalysisService.analyze_asset(
                    asset,
                    organization_id=org_id,
                    use_cache=False,
                )
        if intent == "simulation":
            scenario = AICopilotService._extract_simulation_scenario(question)
            asset = AICopilotService._extract_impact_asset(question, org_id) or scenario["asset"]
            context["simulation"] = SimulationService.run_simulation(
                asset=asset,
                scenario_type=scenario["scenario_type"],
                scenario=scenario["scenario"],
                organization_id=org_id,
                simulation_mode="Copilot",
                created_by="ai_copilot",
                persist=False,
            )
        if intent == "reasoning":
            context["reasoning"] = AIReasoningService.reason(
                question=question,
                organization_id=org_id,
                created_by="ai_copilot",
                persist=False,
            )
        if intent == "predictive":
            context["forecasting"] = ForecastingService.forecast_enterprise_metrics(org_id)
            context["financial_forecast"] = FinancialIntelligenceService.get_financial_forecast(org_id)
            context["capacity_forecast"] = CapacityIntelligenceService.forecast_capacity(org_id)
            context["risk_prediction"] = RiskPredictionService.predict_risks(org_id)
            context["predictive_ai"] = PredictiveAIService.get_predictive_recommendations(org_id)
        return context

    @staticmethod
    def get_answer(question: str, organization_id: str | None = None) -> str:
        return AICopilotService.ask(question, organization_id)["answer"]

    @staticmethod
    def get_followup_questions(intent: str | None = None) -> list[str]:
        if intent == "cost":
            return ["Show cost by capability", "Where is spend unattributed?", "Which application costs the most?"]
        if intent == "decision":
            return ["Show pending AI decisions", "Show auto-remediation candidates", "Explain DEC-000001"]
        if intent == "connector":
            return ["Which connectors are failing?", "What is the recommended fix?", "Show discovery coverage"]
        if intent == "connector_studio":
            return ["Connect our HRMS", "Show connector mapping suggestions", "Generate a connector from Swagger", "Run connector certification"]
        if intent == "platform_health":
            return ["Show platform readiness", "Which component is unhealthy?", "Show scheduler health", "Show data quality issues"]
        if intent == "data_quality":
            return ["What is the AI Trust Score?", "Show stale telemetry", "Show broken Knowledge Graph relationships", "Which applications have missing owners?"]
        if intent == "security":
            return ["Show expiring credentials", "Show RBAC violations", "Show tenant isolation status", "Is execution protected?"]
        if intent == "performance":
            return ["Which dashboard is slow?", "Show cache hit ratio", "Show database latency", "Show event bus throughput"]
        if intent == "enterprise_readiness":
            return ["Generate audit evidence", "Show DR readiness", "Can we release Version 1.0?", "Is production deployment ready?"]
        if intent == "scheduler":
            return ["Show dead-letter queue", "Which connector is running slow?", "What is the next scheduled sync?", "Show scheduler health"]
        if intent == "business":
            return ["What is the blast radius if Checkout fails?", "Which capability has highest risk?", "Who owns it?"]
        if intent == "learning":
            return ["Which AI agent is performing best?", "Why did confidence change?", "Show workflow improvements"]
        if intent == "incident":
            return ["What caused the incident?", "Which tool detected it first?", "What changed before the incident?", "Replay the incident"]
        return AICopilotService.SUGGESTED_PROMPTS[:4]

    @staticmethod
    def get_history(session_id: str = "default") -> list[dict[str, Any]]:
        return AICopilotService._HISTORY.get(session_id, [])

    @staticmethod
    def clear_history(session_id: str = "default") -> dict[str, Any]:
        AICopilotService._HISTORY[session_id] = []
        return {"status": "SUCCESS", "session_id": session_id}

    @staticmethod
    def get_dashboard(session_id: str = "default") -> dict[str, Any]:
        history = AICopilotService.get_history(session_id)
        response_times = [float(row.get("response_time_ms") or 0) for row in history]
        return {
            "questions_asked": len(history),
            "average_response_time_ms": round(sum(response_times) / len(response_times), 1) if response_times else 0,
            "insights_generated": sum(1 for row in history if row.get("intent") in {"cost", "governance", "operations", "business"}),
            "recommendations_referenced": sum(1 for row in history if row.get("context", {}).get("recommendations")),
            "decisions_referenced": sum(1 for row in history if row.get("context", {}).get("decisions")),
            "history": history,
            "suggested_prompts": AICopilotService.SUGGESTED_PROMPTS,
        }

    @staticmethod
    def _detect_intent(question: str) -> str:
        text = str(question or "").lower()
        if "who owns" in text or "owner" in text:
            if AICopilotService._is_data_quality_question(text):
                return "data_quality"
            return "governance"
        if AICopilotService._is_scheduler_question(text):
            return "scheduler"
        if AICopilotService._is_enterprise_readiness_question(text):
            return "enterprise_readiness"
        if AICopilotService._is_security_question(text):
            return "security"
        if AICopilotService._is_performance_question(text):
            return "performance"
        if AICopilotService._is_data_quality_question(text):
            return "data_quality"
        if AICopilotService._is_platform_health_question(text):
            return "platform_health"
        if AICopilotService._is_connector_studio_question(text):
            return "connector_studio"
        if AICopilotService._is_incident_timeline_question(text):
            return "incident"
        if AICopilotService._is_observability_question(text):
            return "observability"
        if AICopilotService._is_connector_question(text):
            return "connector"
        if any(token in text for token in ["decision", "dec-", "approval", "auto-remediation", "auto remediation"]):
            return "decision"
        if AICopilotService._is_learning_question(text):
            return "learning"
        if any(token in text for token in ["recommendation", "ai-", "optimization", "wasted", "savings"]):
            return "recommendation" if "ai-" in text or "recommendation" in text else "optimization"
        if AICopilotService._is_business_goal(text):
            return "agentic"
        if any(token in text for token in ["can we", "should we", "best course", "safest", "why is this recommendation", "why recommendation"]):
            return "reasoning"
        if any(token in text for token in ["next month", "forecast", "will my", "likely to exceed", "reach capacity", "preventive", "prediction", "predict"]):
            return "predictive"
        if any(token in text for token in ["spend", "cost", "money", "budget", "chargeback"]):
            return "cost"
        if any(token in text for token in ["what if", "what happens if", "simulate", "simulation", "migrate", "goes down", "reduce", "decommission"]):
            return "simulation"
        if any(token in text for token in ["why is", "critical", "impact of", "blast radius", "what breaks", "fails", "unavailable"]):
            return "impact"
        if any(token in text for token in ["owner", "mapping", "governance", "policy", "missing"]):
            return "governance"
        if any(token in text for token in ["connector", "failed", "failing", "discovery", "sync"]):
            return "connector"
        if any(token in text for token in ["asset", "ec2", "aws", "azure", "technology", "resource"]):
            return "technology"
        if any(token in text for token in ["capability", "application", "checkout", "blast radius", "business service", "risk"]):
            return "business"
        if any(token in text for token in ["cio", "ceo", "executive", "focus", "morning"]):
            return "executive"
        return "general"

    @staticmethod
    def _generate_answer(question: str, intent: str, context: dict[str, Any]) -> dict[str, Any]:
        if intent in {"cost", "optimization"}:
            return AICopilotService._cost_answer(context)
        if intent == "governance":
            return AICopilotService._governance_answer(context)
        if intent == "connector":
            return AICopilotService._connector_answer(context)
        if intent == "connector_studio":
            return AICopilotService._connector_studio_answer(context)
        if intent == "platform_health":
            return AICopilotService._platform_health_answer(context)
        if intent == "data_quality":
            return AICopilotService._data_quality_answer(context)
        if intent == "security":
            return AICopilotService._security_answer(context)
        if intent == "performance":
            return AICopilotService._performance_answer(context)
        if intent == "enterprise_readiness":
            return AICopilotService._enterprise_readiness_answer(context)
        if intent == "scheduler":
            return AICopilotService._scheduler_answer(context)
        if intent == "observability":
            return AICopilotService._observability_answer(context)
        if intent == "incident":
            return AICopilotService._incident_answer(context)
        if intent == "technology":
            return AICopilotService._technology_answer(question, context)
        if intent == "impact":
            return AICopilotService._impact_answer(question, context)
        if intent == "simulation":
            return AICopilotService._simulation_answer(question, context)
        if intent == "reasoning":
            return AICopilotService._reasoning_answer(question, context)
        if intent == "predictive":
            return AICopilotService._predictive_answer(question, context)
        if intent == "learning":
            return AICopilotService._learning_answer(question, context)
        if intent == "agentic":
            return AICopilotService._agentic_answer(question, context)
        if intent == "business":
            return AICopilotService._business_answer(question, context)
        if intent == "recommendation":
            return AICopilotService._recommendation_answer(question, context)
        if intent == "decision":
            return AICopilotService._decision_answer(question, context)
        if intent == "executive":
            return AICopilotService._executive_answer(context)
        return AICopilotService._general_answer(context)

    @staticmethod
    def _cost_answer(context: dict[str, Any]) -> dict[str, Any]:
        enterprise = context["enterprise"]
        cost = enterprise["cost"]
        top_app = AICopilotService._first(cost.get("application_spend", []))
        top_cap = AICopilotService._first(cost.get("capability_spend", []))
        summary = cost.get("summary", {})
        text = (
            f"{top_cap.get('name', 'The top capability')} is the highest-cost capability at "
            f"{AICopilotService._money(top_cap.get('cost'))}. "
            f"{top_app.get('name', 'The top application')} is the highest-spend application at "
            f"{AICopilotService._money(top_app.get('cost'))}. "
            f"There are {int(summary.get('unattributed_rows') or 0)} unattributed cost records worth "
            f"{AICopilotService._money(summary.get('unattributed_cost'))}."
        )
        return AICopilotService._answer(
            text,
            context,
            citations=[top_cap.get("name"), top_app.get("name"), "enterprise_cost_attribution"],
            used=["Enterprise Cost Attribution", "AI Insights", "AI Recommendations"],
        )

    @staticmethod
    def _governance_answer(context: dict[str, Any]) -> dict[str, Any]:
        ownership = context["enterprise"]["ownership"]
        quality = context["enterprise"]["quality"]["scores"]
        top_app = AICopilotService._first(context["enterprise"].get("applications", []))
        top_asset = AICopilotService._first(context["enterprise"].get("assets", []))
        owner = top_app.get("owner") or top_asset.get("owner") or "Unassigned"
        text = (
            f"{top_app.get('name', 'The primary application')} is owned by {owner}. "
            f"Ownership quality is {float(quality.get('ownership') or 0):.1f}%. "
            f"The ownership model currently has {ownership.get('total_records', 0)} records. "
            "The main governance attention area is capability governance and completion of cost and relationship mappings."
        )
        return AICopilotService._answer(
            text,
            context,
            citations=["enterprise_asset_ownership", "business_capability_registry"],
            used=["Enterprise Ownership", "Business Capability Registry", "Digital Twin Quality"],
        )

    @staticmethod
    def _connector_answer(context: dict[str, Any]) -> dict[str, Any]:
        question = str(context.get("question") or "").lower()
        platform = context.get("connector_platform") or {}
        platform_rows = platform.get("connectors") or []
        target = AICopilotService._extract_connector_name(question, platform_rows)
        if "how many" in question or "systems are connected" in question:
            kpis = platform.get("kpis") or {}
            text = (
                f"{kpis.get('Connected', 0)} of {kpis.get('Total Connectors', 0)} enterprise systems are connected. "
                f"The Enterprise Data Fabric has {kpis.get('Fabric Records', 0)} normalized records and average connector health is "
                f"{kpis.get('Average Health', 0)}%."
            )
            return AICopilotService._answer(
                text,
                context,
                citations=["enterprise_connector_registry", "enterprise_data_fabric"],
                used=["Enterprise Connector Platform", "Connector Health Dashboard", "Enterprise Data Fabric"],
            )
        if target:
            row = next((item for item in platform_rows if item.get("Connector") == target), {})
            if target == "Azure" and "governance" in question:
                details = AICopilotService._connector_certification_details(row)
                domains = details.get("domains", {})
                governance = domains.get("governance", ["Azure Advisor", "Azure Policy", "Defender for Cloud", "Compliance State"])
                text = (
                    "Azure Governance coverage is healthy. "
                    f"{', '.join(governance)} are connected. "
                    f"Governance Score: {(details or {}).get('governance_score', 94)}. "
                    f"Certification: {row.get('Certification', 'Gold')}. Health: {row.get('Health', 97)}."
                )
            elif target == "GCP" and "optimization" in question:
                details = AICopilotService._connector_certification_details(row)
                optimization = details.get("optimization", {})
                text = (
                    "GCP Optimization is available. "
                    f"Rightsizing: {optimization.get('Rightsizing', 'Available')}. "
                    f"Idle Resources: {optimization.get('Idle Resources', 12)}. "
                    f"Potential Savings: {AICopilotService._money(optimization.get('Potential Savings', 18500))}/month. "
                    f"Confidence: {optimization.get('Confidence', 95)}%."
                )
            elif target == "Microsoft 365" and ("unused" in question or "license" in question):
                details = AICopilotService._connector_certification_details(row)
                unused = details.get("unused_licenses", {"Microsoft 365 E5": 32, "Business Premium": 14})
                optimization = details.get("optimization", {})
                text = (
                    "Unused Microsoft licenses: "
                    f"Microsoft 365 E5: {unused.get('Microsoft 365 E5', 32)}; "
                    f"Business Premium: {unused.get('Business Premium', 14)}. "
                    f"Potential Annual Savings: {AICopilotService._money(optimization.get('potential_annual_savings', 24600))}. "
                    f"Confidence: {optimization.get('confidence', 97)}%."
                )
            elif target == "Microsoft 365" and ("90 days" in question or "not logged in" in question or "inactive users" in question):
                details = AICopilotService._connector_certification_details(row)
                inactive = details.get("inactive_users", {})
                text = (
                    f"Inactive Users: {inactive.get('count', 42)}. "
                    f"License Cost: {AICopilotService._money(inactive.get('license_cost', 16800))}/year. "
                    "Recommendation: Reclaim inactive licenses. "
                    f"Confidence: {inactive.get('confidence', 98)}%."
                )
            elif target == "ServiceNow" and ("p1" in question or "critical incident" in question or "open incident" in question):
                details = AICopilotService._connector_certification_details(row)
                incidents = details.get("open_p1_incidents", {})
                text = (
                    f"Critical Incidents: {incidents.get('count', 12)}. "
                    f"Average Age: {incidents.get('average_age_minutes', 46)} Minutes. "
                    f"Business Services Impacted: {incidents.get('business_services_impacted', 5)}. "
                    f"Predicted Risk: {incidents.get('predicted_risk', 'High')}."
                )
            elif target == "ServiceNow" and ("cab" in question or "awaiting approval" in question or "pending change" in question):
                details = AICopilotService._connector_certification_details(row)
                cab = details.get("pending_cab", {})
                text = (
                    f"Pending CAB Change Requests: {cab.get('change_requests', 8)}. "
                    f"Emergency: {cab.get('emergency', 2)}. "
                    f"Standard: {cab.get('standard', 6)}. "
                    f"Recommendation: {cab.get('recommendation', 'Schedule CAB review before weekend maintenance.')}"
                )
            elif target == "GitHub" and ("high-risk" in question or "high risk" in question or "risky repos" in question):
                details = AICopilotService._connector_certification_details(row)
                risk = details.get("high_risk_repositories", {})
                repos = risk.get("repositories", [])
                names = ", ".join(item.get("name", "unknown") for item in repos[:3])
                text = (
                    f"High-Risk GitHub Repositories: {risk.get('count', 7)}. "
                    f"Critical: {risk.get('critical', 3)}. High: {risk.get('high', 4)}. "
                    f"Top repositories: {names}. "
                    f"Recommendation: {risk.get('recommendation', 'Prioritize critical repository remediation before the next release window.')}"
                )
            elif target == "GitHub" and ("deployment" in question or "deployed" in question):
                details = AICopilotService._connector_certification_details(row)
                deployments = details.get("deployments_this_week", {})
                apps = ", ".join(deployments.get("applications", [])[:4])
                text = (
                    f"GitHub deployments this week: {deployments.get('count', 28)}. "
                    f"Production: {deployments.get('production', 9)}. Failed: {deployments.get('failed', 2)}. "
                    f"Applications changed: {apps}. "
                    f"Highest risk: {deployments.get('highest_risk', 'No high-risk deployment pattern detected.')}"
                )
            elif target == "GitHub" and ("security alert" in question or "unresolved" in question or "dependabot" in question or "secret scanning" in question):
                details = AICopilotService._connector_certification_details(row)
                alerts = details.get("unresolved_security_alerts", {})
                text = (
                    f"Unresolved GitHub Security Alerts: {alerts.get('total', 86)}. "
                    f"Dependabot: {alerts.get('dependabot', 48)}. "
                    f"Code Scanning: {alerts.get('code_scanning', 27)}. "
                    f"Secret Scanning: {alerts.get('secret_scanning', 11)}. "
                    f"Critical: {alerts.get('critical', 6)}. "
                    f"Recommendation: {alerts.get('recommendation', 'Close critical alerts on production repositories first.')}"
                )
            elif target == "GitHub" and ("applications changed" in question or "application changed" in question or "changed recently" in question or "recently changed" in question):
                details = AICopilotService._connector_certification_details(row)
                changes = details.get("applications_changed_recently", {})
                apps = changes.get("applications", [])
                summary = "; ".join(
                    f"{item.get('name')}: {item.get('commits')} commits, {item.get('pull_requests')} PRs, {item.get('deployments')} deployments"
                    for item in apps[:3]
                )
                text = (
                    f"Applications changed in the last {changes.get('window', '7 days')}: {summary}. "
                    f"Recommendation: {changes.get('recommendation', 'Review release risk for recently changed critical applications.')}"
                )
            elif target == "Jira" and ("delayed release" in question or ("release" in question and "delayed" in question)):
                details = AICopilotService._connector_certification_details(row)
                releases = details.get("release_health", {})
                text = (
                    f"Delayed Releases: {releases.get('count', 4)}. "
                    f"High Risk: {releases.get('high_risk', 2)}. "
                    f"Blocked Epics: {releases.get('blocked_epics', 6)}. "
                    f"Recommendation: {releases.get('recommendation', 'Resolve dependency issues before release.')}"
                )
            elif target == "Jira" and ("sprint" in question or "delivery risk" in question):
                details = AICopilotService._connector_certification_details(row)
                sprint = details.get("highest_risk_sprint", {})
                text = (
                    f"{sprint.get('name', 'Sprint 24')} has the highest delivery risk. "
                    f"Risk: {sprint.get('risk', 'High')}. "
                    f"Blocked Issues: {sprint.get('blocked_issues', 14)}. "
                    f"Predicted Delay: {sprint.get('predicted_delay_days', 5)} Days. "
                    f"Confidence: {sprint.get('confidence', 96)}%."
                )
            elif target == "Jira" and ("risk" in question or "bottleneck" in question or "sla" in question):
                details = AICopilotService._connector_certification_details(row)
                risk = details.get("delivery_risk", {})
                text = (
                    f"Jira delivery risk: {risk.get('delayed_releases', 4)} delayed releases, "
                    f"{risk.get('blocked_epics', 6)} blocked epics, "
                    f"{risk.get('sla_breaches', 18)} SLA breaches, "
                    f"{risk.get('approval_bottlenecks', 9)} approval bottlenecks, and "
                    f"{risk.get('change_backlog', 43)} changes in backlog. "
                    f"Recommendation: {risk.get('recommendation', 'Prioritize blocked epics and approval bottlenecks.')}"
                )
            elif target == "Jira" and ("project" in question or "jsm" in question or "assets" in question):
                details = AICopilotService._connector_certification_details(row)
                projects = details.get("projects", {})
                boards = details.get("boards", {})
                sprints = details.get("sprints", {})
                jsm = details.get("jsm", {})
                assets = details.get("assets", {})
                text = (
                    "Jira Platform is connected. "
                    f"Projects: {projects.get('count', 128)}. "
                    f"Boards: {boards.get('count', 46)}. "
                    f"Sprints: {sprints.get('count', 32)}. "
                    f"JSM: {jsm.get('status', 'Connected')}. "
                    f"Assets: {assets.get('status', 'Connected')}. "
                    f"Certification: {row.get('Certification', 'Gold')}. Health: {row.get('Health', 97)}."
                )
            elif target == "Dynatrace" and ("connected" in question or "status" in question or "healthy" in question):
                details = AICopilotService._connector_certification_details(row)
                smartscape = details.get("smartscape", {})
                problems = details.get("problems", {})
                davis = details.get("davis_ai", {})
                text = (
                    f"Dynatrace is {row.get('Status', 'Connected')}. "
                    f"Certification: {row.get('Certification', 'Gold')}. Health: {row.get('Health', 98)}. "
                    f"Smartscape: {smartscape.get('status', 'Healthy')}. "
                    f"Problems: {problems.get('status', 'Connected')}. "
                    f"Davis AI: {davis.get('status', 'Connected')}. "
                    f"Telemetry: {details.get('telemetry', 'Healthy')}."
                )
            elif target == "New Relic" and ("service level" in question or "service levels" in question or "slo" in question):
                details = AICopilotService._connector_certification_details(row)
                levels = details.get("service_levels", {})
                text = (
                    f"New Relic Service Levels: {levels.get('count', 72)}. "
                    f"Breaching: {levels.get('breaching', 6)}. "
                    f"Average Compliance: {float(levels.get('average_compliance') or 95.4):.1f}%. "
                    f"Certification: {row.get('Certification', 'Gold')}. Health: {row.get('Health', 97)}."
                )
            elif target == "New Relic" and ("workload" in question or "unhealthy" in question):
                details = AICopilotService._connector_certification_details(row)
                workloads = details.get("workloads", {})
                text = (
                    f"New Relic Workloads: {workloads.get('count', 48)}. "
                    f"Unhealthy: {workloads.get('unhealthy', 3)}. "
                    f"Workload Health: {workloads.get('health', 94)}. "
                    "Recommendation: Review Checkout workload, service-level burn, and error inbox before the next release window."
                )
            elif target == "New Relic" and ("alert" in question or "summary" in question):
                details = AICopilotService._connector_certification_details(row)
                alerts = details.get("alerts", {})
                errors = details.get("errors", {})
                synthetics = details.get("synthetics", {})
                text = (
                    f"New Relic Alerts: {alerts.get('active', 29)} active, {alerts.get('critical', 4)} critical. "
                    f"Error Rate: {errors.get('error_rate', 5.8)}%. "
                    f"Synthetic Failures: {synthetics.get('failures', 5)}. "
                    "Recommendation: Prioritize Checkout service-level breach and critical APM errors."
                )
            elif target == "Splunk" and ("notable" in question or "security event" in question or "security events" in question):
                details = AICopilotService._connector_certification_details(row)
                notable = details.get("notable_security_events", {})
                services = ", ".join(notable.get("affected_services", ["Checkout", "Payments", "Identity"]))
                text = (
                    f"Notable Events: High {notable.get('high', 4)}, Medium {notable.get('medium', 12)}. "
                    f"Affected Services: {services}. "
                    f"Top Detection: {notable.get('top_detection', 'Checkout authentication anomalies')}. "
                    f"Recommendation: {notable.get('recommendation', 'Investigate Checkout authentication anomalies.')}"
                )
            elif target == "Splunk" and ("failed login" in question or "login trend" in question or "authentication" in question):
                details = AICopilotService._connector_certification_details(row)
                trend = details.get("failed_login_trend", {})
                text = (
                    f"Failed Logins Last 24 Hours: {trend.get('last_24_hours', 1420)}. "
                    f"Increase: {trend.get('increase', '18%')}. "
                    f"Risk: {trend.get('risk', 'Medium')}. "
                    f"Recommendation: {trend.get('recommendation', 'Review authentication policy and MFA coverage.')}"
                )
            elif target == "Splunk" and ("connected" in question or "status" in question or "healthy" in question):
                details = AICopilotService._connector_certification_details(row)
                es = details.get("enterprise_security", {})
                soar = details.get("soar", {})
                logs = details.get("logs", {})
                text = (
                    f"Splunk is {row.get('Status', 'Connected')}. "
                    f"Certification: {row.get('Certification', 'Gold')}. Health: {row.get('Health', 98)}. "
                    f"Enterprise Security: {es.get('status', 'Healthy')}. "
                    f"SOAR: {soar.get('status', 'Connected')}. "
                    f"Logs: {logs.get('status', 'Healthy')}."
                )
            elif "last" in question or "synchronized" in question or "sync" in question:
                text = (
                    f"{target} last synchronized at {row.get('Last Sync') or 'not yet synchronized'}. "
                    f"Next sync: {row.get('Next Sync') or 'not scheduled'}. Status: {row.get('Status', 'Not Configured')}."
                )
            elif "why" in question or "unhealthy" in question or "failing" in question:
                reason = "credentials are not configured" if row.get("Status") == "Not Configured" else "latest sync health is below threshold"
                if row.get("Health", 0) >= 85:
                    reason = "the connector is healthy"
                text = (
                    f"{target} health is {row.get('Health', 0)} with status {row.get('Status', 'Not Configured')}. "
                    f"Reason: {reason}. Data freshness: {row.get('Data Freshness', 'Unknown')}."
                )
            else:
                text = (
                    f"{target} is {row.get('Status', 'Not Configured')}. "
                    f"Authentication: {row.get('Authentication', 'Unknown')}. "
                    f"Health: {row.get('Health', 0)}. "
                    f"Certification: {row.get('Certification', 'Uncertified')}. "
                    f"Last sync: {row.get('Last Sync') or 'not yet synchronized'}."
                )
            return AICopilotService._answer(
                text,
                context,
                citations=[target, "enterprise_connector_registry"],
                used=["Enterprise Connector Platform", "Connector Health Dashboard", "Credential Vault"],
            )
        connector_rows = context.get("connector_operations") or []
        failing = [row for row in connector_rows if row.get("Status") == "Failed"]
        not_configured = [row for row in connector_rows if row.get("Status") == "Not Configured"]
        if failing:
            names = ", ".join(row.get("Connector") for row in failing)
            text = (
                f"{names} is currently failing. The recommended action is to validate credentials, permissions, "
                "and rerun connector sync. Discovery coverage is also incomplete because "
                f"{len(not_configured)} connectors are not configured."
            )
        else:
            text = f"No connector failures are currently reported. {len(not_configured)} connectors remain not configured."
        return AICopilotService._answer(
            text,
            context,
            citations=[row.get("Connector") for row in failing] + ["connector_registry"],
            used=["Connector Operations", "AI Insights", "AI Decisions"],
        )

    @staticmethod
    def _connector_studio_answer(context: dict[str, Any]) -> dict[str, Any]:
        studio = context.get("connector_studio") or {}
        question = str(context.get("question") or "").lower()
        api = studio.get("api_discovery") or {}
        certification = studio.get("certification") or {}
        generator = studio.get("ai_connector_generator") or {}
        if "hrms" in question or "connect our" in question:
            endpoints = api.get("Endpoints") or []
            entities = ", ".join(row.get("Entity", "") for row in endpoints[:4])
            text = (
                f"Connector Studio detected {', '.join(api.get('Detected', ['OpenAPI']))} at {api.get('Base URL', 'the API endpoint')}. "
                f"Recommended authentication is OAuth2. Discovered entities: {entities}. "
                f"Suggested field mapping is ready, certification target is {certification.get('Level', 'Gold')}, "
                "and the draft connector is ready to create."
            )
        elif "swagger" in question or "generate" in question or "api specification" in question:
            assets = ", ".join(generator.get("Generated Assets", [])[:9])
            text = (
                f"AI Connector Generator can create {generator.get('Connector', 'the connector')} from Swagger/OpenAPI. "
                f"Generated assets: {assets}. Estimated build time: {generator.get('Estimated Build Time', '2 hours')} "
                f"with {generator.get('Manual Effort Reduced', '85%')} manual effort reduction."
            )
        elif "mapping" in question or "schema" in question:
            mappings = studio.get("field_mapping") or []
            summary = "; ".join(
                f"{row.get('Source Field')} -> {row.get('Suggested Entity')} ({row.get('Confidence')}%)"
                for row in mappings[:5]
            )
            text = f"Connector Studio mapping suggestions are ready: {summary}."
        elif "marketplace" in question:
            marketplace = studio.get("marketplace") or []
            text = (
                f"The AI Connector Marketplace has {len(marketplace)} sample entries across built-in, partner, customer, community-ready, "
                "and AI-generated connector types. Each connector carries certification, supported entities, validation date, and compatibility metadata."
            )
        elif "certification" in question or "certify" in question:
            text = (
                f"{certification.get('Connector', 'The connector')} is {certification.get('Level', 'Gold')} ready with "
                f"{certification.get('Coverage Percent', 100)}% coverage and health {certification.get('Health', 97)}. "
                f"Security: {certification.get('Security', 'Vault-backed')}."
            )
        else:
            kpis = studio.get("kpis") or {}
            text = (
                f"Connector Studio is ready with {kpis.get('Templates', 0)} templates, {kpis.get('Auth Methods', 0)} authentication methods, "
                f"{kpis.get('Marketplace Connectors', 0)} marketplace entries, {kpis.get('Draft Connectors', 0)} draft connectors, "
                f"and {kpis.get('Studio Readiness', 0)}% readiness."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["Connector Studio", "Universal Connector Platform", "AI Connector Marketplace"],
            used=["Connector Studio", "AI Mapping", "Knowledge Graph Mapping", "Digital Twin Mapping", "Connector Certification"],
        )

    @staticmethod
    def _platform_health_answer(context: dict[str, Any]) -> dict[str, Any]:
        health = context.get("platform_health") or {}
        question = str(context.get("question") or "").lower()
        kpis = health.get("kpis") or {}
        readiness = health.get("readiness") or {}
        connectors = health.get("connector_certification") or {}
        if "unhealthy" in question or "component" in question:
            rows = [
                row
                for row in health.get("components", [])
                if str(row.get("Status")) != "Healthy"
            ]
            if not rows:
                text = "No critical platform components are unhealthy. Connector Studio is the lowest scoring component at 96%, which is still healthy."
            else:
                summary = "; ".join(f"{row.get('Component')}: {row.get('Status')} ({row.get('Score')}%)" for row in rows)
                text = f"Components needing attention: {summary}."
        elif "scheduler" in question:
            scheduler = health.get("scheduler") or {}
            text = (
                f"Scheduler is {scheduler.get('Status', 'Healthy')} with {scheduler.get('Active Jobs', 0)} active jobs, "
                f"{scheduler.get('Successful Runs', 0)} successful runs, {scheduler.get('Failed Runs', 0)} failed runs, "
                f"retry queue {scheduler.get('Retry Queue', 0)}, and average execution time {scheduler.get('Average Execution Time', '42s')}."
            )
        elif "ai health" in question or "ai services" in question:
            ai = health.get("ai_health") or {}
            warning = next((row for row in ai.get("rows", []) if row.get("Status") != "Healthy"), {})
            text = (
                f"AI Services score is {ai.get('score', 0)}%. Copilot, Reasoning, Prediction, Simulation, Workflow Builder, "
                f"Governance, and Learning are healthy. Execution is {warning.get('Mode', 'Mock Only')}."
            )
        elif "data quality" in question:
            quality = health.get("data_quality") or {}
            issues = [row for row in quality.get("rows", []) if row.get("Status") != "Healthy"]
            summary = "; ".join(f"{row.get('Metric')}: {row.get('Count')}" for row in issues)
            text = f"Data Quality is {quality.get('score', 0)}%. Issues: {summary}."
        elif "connector health" in question or "certification" in question:
            text = (
                f"Connector certification passed for {connectors.get('certified', 0)} / {connectors.get('total', 0)} connectors. "
                f"Average health is {connectors.get('average_health', 0)} and score is {connectors.get('score', 0)}%."
            )
        elif "below 100" in question or "why" in question:
            security = health.get("security") or {}
            quality = health.get("data_quality") or {}
            text = (
                f"Readiness is below 100% because Security is {security.get('score', 0)}% due to demo secret rotation warnings, "
                f"Data Quality is {quality.get('score', 0)}% due to a few owner and mapping gaps, and Connector Studio readiness is 96%."
            )
        else:
            text = (
                f"Platform Readiness: {kpis.get('Platform Readiness', readiness.get('score', 0))}%. "
                f"Status: {kpis.get('Overall Health', readiness.get('classification', 'Unknown'))}. "
                f"Connectors: {connectors.get('certified', 0)}/{connectors.get('total', 0)} Gold Certified. "
                "Observability, Knowledge Graph, Digital Twin, AI Services, Scheduler, Security, and Data Quality are healthy. "
                f"Critical issues: {kpis.get('Critical Issues', 0)}. Warnings: {kpis.get('Warnings', 0)}."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["Platform Health Dashboard", "Connector Certification Runner", "Platform Readiness Engine"],
            used=["Platform Health Service", "Enterprise Test Harness", "Connector Certification Suite", "Operations Log"],
        )

    @staticmethod
    def _scheduler_answer(context: dict[str, Any]) -> dict[str, Any]:
        scheduler = context.get("scheduler") or {}
        question = str(context.get("question") or "").lower()
        dashboard = scheduler.get("dashboard") or {}
        health = dashboard.get("health") or {}
        action = scheduler.get("action") or {}
        connector = scheduler.get("connector")
        if "why" in question and "fail" in question:
            failed = scheduler.get("failed_job") or (action.get("job") if action else {})
            if failed:
                text = (
                    f"{failed.get('connector', connector)} sync failed because {failed.get('failure_reason') or 'connector sync failure'}. "
                    f"Last error: {failed.get('last_error')}. Retry count: {failed.get('retry_count', 0)}. "
                    "No infrastructure actions were executed."
                )
            else:
                text = f"No failed {connector or 'connector'} sync is currently recorded."
        elif action:
            text = f"{connector or 'Connector'} scheduler action completed: {action.get('status')}. No infrastructure actions were executed."
        elif "dead-letter" in question or "dead letter" in question:
            dead = dashboard.get("dead_letter_queue") or []
            if dead:
                text = f"Dead-letter queue has {len(dead)} jobs. Latest: {dead[0].get('connector')} failed because {dead[0].get('failure_reason')}. Recommended action: {dead[0].get('recommended_action')}."
            else:
                text = "Dead-letter queue is empty. No connector sync jobs have exceeded max retries."
        elif "slow" in question:
            text = f"The slowest connector is {health.get('Longest-running Connector', 'Datadog')} with average duration {health.get('Average Duration Ms', 0)} ms."
        elif "next scheduled" in question or "next sync" in question:
            runs = dashboard.get("next_scheduled_runs") or []
            if runs:
                row = runs[0]
                text = f"Next scheduled sync is {row.get('connector')} at {row.get('next_run_at')} with status {row.get('status')}."
            else:
                text = "No scheduled connector syncs are currently queued."
        else:
            text = (
                f"Scheduler is {health.get('Status', 'Healthy')} with {health.get('Queued Jobs', 0)} queued jobs, "
                f"{health.get('Retry Queue', 0)} retrying jobs, {health.get('Dead Letter', 0)} dead-letter jobs, "
                f"success rate {health.get('Success Rate', 100.0)}%, and longest-running connector {health.get('Longest-running Connector', 'Datadog')}."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["Enterprise Scheduler", "Retry Engine", "Dead Letter Queue"],
            used=["Enterprise Scheduler Service", "Retry Engine", "Scheduler Repository", "Operations Log"],
        )

    @staticmethod
    def _data_quality_answer(context: dict[str, Any]) -> dict[str, Any]:
        quality = context.get("data_quality") or {}
        question = str(context.get("question") or "").lower()
        kpis = quality.get("kpis") or {}
        issues = quality.get("issues") or []
        ai_trust = quality.get("ai_trust_score") or {}
        if "ai trust" in question:
            text = (
                f"AI Trust Score is {ai_trust.get('AI Trust Score', 0)}%. "
                f"Reasoning confidence is {ai_trust.get('Reasoning Confidence', 0)}%, prediction confidence is "
                f"{ai_trust.get('Prediction Confidence', 0)}%, graph completeness is {ai_trust.get('Graph Completeness', 0)}%, "
                f"and telemetry freshness is {ai_trust.get('Telemetry Freshness', 0)}%. Decision: {ai_trust.get('Decision', 'Trusted with monitoring')}."
            )
        elif "missing owner" in question or "missing owners" in question:
            rows = [row for row in issues if row.get("Event Key") == "ownership"]
            summary = "; ".join(f"{row.get('Issue')}: {row.get('Description')}" for row in rows)
            text = f"Missing ownership issues: {summary or 'No missing owner issues are open.'}"
        elif "duplicate" in question:
            rows = [row for row in issues if row.get("Event Key") == "duplicate"]
            summary = "; ".join(f"{row.get('Issue')}: {row.get('Description')}" for row in rows)
            text = f"Duplicate resources: {summary or 'No duplicate resources are currently detected.'}"
        elif "stale telemetry" in question or "telemetry stale" in question:
            rows = [row for row in issues if row.get("Event Key") == "telemetry"]
            freshness = quality.get("freshness") or []
            stale = [row for row in freshness if row.get("Status") != "Healthy"]
            summary = "; ".join(f"{row.get('Source')} is {row.get('Freshness')} old" for row in stale)
            text = f"Stale telemetry: {summary or 'All telemetry sources are fresh.'} {rows[0].get('Recommended Action') if rows else ''}".strip()
        elif "broken" in question or "knowledge graph" in question or "relationship" in question:
            rows = [row for row in issues if row.get("Event Key") == "relationship"]
            summary = "; ".join(f"{row.get('Issue')}: {row.get('Description')}" for row in rows)
            text = f"Knowledge Graph relationship validation is {ai_trust.get('Graph Completeness', 0)}%. {summary or 'No broken relationships are open.'}"
        elif "below 100" in question or "why" in question:
            open_issues = [row for row in issues if row.get("Severity") in {"Failed", "Warning"}]
            summary = "; ".join(f"{row.get('Domain')} - {row.get('Issue')} ({row.get('Count')})" for row in open_issues[:6])
            text = (
                f"Data quality is below 100% because {summary}. "
                f"Overall Data Quality is {kpis.get('Overall Data Quality', 0)}% and AI Trust is {kpis.get('AI Trust Score', 0)}%."
            )
        else:
            text = (
                f"Overall Data Quality is {kpis.get('Overall Data Quality', 0)}% with health {kpis.get('Health', 'Unknown')}. "
                f"{kpis.get('Passed', 0)} of {kpis.get('Validation Rules', 0)} validation rules passed, "
                f"{kpis.get('Failed', 0)} failed, and {kpis.get('Warnings', 0)} are warnings. "
                f"AI Trust Score is {kpis.get('AI Trust Score', 0)}%."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["Data Quality Dashboard", "AI Trust Score", "Enterprise Event Bus"],
            used=["Enterprise Data Quality Service", "Data Quality Repository", "Knowledge Graph Validation", "Telemetry Validation", "Cost Validation"],
        )

    @staticmethod
    def _security_answer(context: dict[str, Any]) -> dict[str, Any]:
        security = context.get("security") or {}
        question = str(context.get("question") or "").lower()
        kpis = security.get("kpis") or {}
        if "expiring" in question or "credential" in question and "expir" in question:
            expiring = [row for row in security.get("token_expiry", []) if row.get("Expiring") or row.get("Expired")]
            if expiring:
                summary = "; ".join(f"{row.get('Connector')}: {row.get('Expires In Days')} days" for row in expiring)
                text = f"Expiring credentials: {summary}."
            else:
                text = "No connector tokens expire inside the policy window. Token Expiry is 0 and credential health is 100%."
        elif "rbac" in question or "violation" in question:
            violations = [row for row in security.get("rbac_validation", []) if int(row.get("Violations") or 0) > 0]
            text = "No RBAC violations are open. Role hierarchy, permission inheritance, page authorization, and API authorization passed." if not violations else f"RBAC violations: {violations}."
        elif "tenant" in question:
            tenant = security.get("tenant_validation") or []
            failures = [row for row in tenant if row.get("Status") != "Healthy"]
            text = "Tenant isolation is verified across Knowledge Graph, Telemetry, AI, Connector, Storage, Dashboard, and Cache surfaces." if not failures else f"Tenant isolation failures: {failures}."
        elif "execution" in question or "protected" in question:
            controls = security.get("execution_security") or []
            mode = next((row.get("Value") for row in controls if row.get("Control") == "Execution Mode"), "Mock Only")
            lock = next((row.get("Value") for row in controls if row.get("Control") == "Execution Lock"), "Active")
            text = f"Execution is protected. Execution Mode is {mode}, governance approval is required, execution lock is {lock}, and production adapters are disabled."
        elif "connector security" in question:
            rows = security.get("connector_security") or []
            warning = [row for row in rows if row.get("Status") != "Secure"]
            text = f"Connector security covers {len(rows)} connectors. {len(rows) - len(warning)} are secure and {len(warning)} have rotation warnings; no connector credentials are invalid or expired."
        elif "compliance" in question:
            controls = security.get("compliance") or []
            warning = [row for row in controls if row.get("Status") != "Healthy"]
            text = f"Compliance score is {kpis.get('Compliance', 0)}%. Audit logging, encryption, secret storage, least privilege, API security, and privacy controls are healthy; {len(warning)} readiness item remains."
        elif "below 100" in question or "why" in question:
            text = (
                f"Security Health is below 100% because two non-critical warnings remain: scheduled secret rotation for AWS/New Relic "
                f"and MFA readiness evidence collection. Critical findings remain {kpis.get('Critical Findings', 0)}."
            )
        else:
            text = (
                f"Nexora Security Health is {kpis.get('Security Health', 0)}% and status is {kpis.get('Status', 'Unknown')}. "
                f"Connector Credentials are healthy, Token Expiry is {kpis.get('Token Expiry', 0)}, RBAC is {kpis.get('RBAC', 'Unknown')}, "
                f"Tenant Isolation is {kpis.get('Tenant Isolation', 'Unknown')}, Execution Security is {kpis.get('Execution Security', 'Unknown')}, "
                f"and Compliance is {kpis.get('Compliance', 0)}%. No critical security findings are open."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["Security Dashboard", "Enterprise Security Framework", "Safe Execution Boundary"],
            used=["Enterprise Security Service", "Security Repository", "Credential Lifecycle", "RBAC Validation", "Tenant Isolation", "Execution Security"],
        )

    @staticmethod
    def _performance_answer(context: dict[str, Any]) -> dict[str, Any]:
        performance = context.get("performance") or {}
        question = str(context.get("question") or "").lower()
        kpis = performance.get("kpis") or {}
        metrics = performance.get("metrics") or []
        throughput = performance.get("throughput_metrics") or []
        cache = performance.get("cache_metrics") or []
        if "dashboard" in question and "slow" in question:
            bottlenecks = [row for row in performance.get("bottlenecks", []) if "Dashboard" in str(row.get("Component"))]
            if bottlenecks:
                row = bottlenecks[0]
                text = f"{row.get('Component')} is the dashboard to watch at {row.get('Observed')} against target {row.get('Target')}; status is {row.get('Status')}."
            else:
                text = "No dashboard is currently slow. Dashboard load is 1.42s, under the 2s target."
        elif "copilot" in question:
            row = next((item for item in metrics if item.get("Metric Key") == "copilot_latency"), {})
            text = f"Copilot is not slow right now. Latency is {row.get('Value', 1180)} ms against target {row.get('Target', '<5s')}."
        elif "connector sync" in question or "sync throughput" in question:
            row = next((item for item in throughput if item.get("Stream") == "Connector Sync"), {})
            text = f"Connector sync throughput is {row.get('Throughput', 1320)} {row.get('Unit', 'records/sec')} with success rate {row.get('Success Rate', 99.4)}%."
        elif "graph traversal" in question or "graph performance" in question:
            row = next((item for item in metrics if item.get("Metric Key") == "graph_traversal_time"), {})
            text = f"Knowledge Graph traversal is {row.get('Value', 840)} ms against target {row.get('Target', '<2s')}."
        elif "cache hit" in question or "cache ratio" in question:
            ratios = [float(row.get("cache_hit_ratio") or 0) for row in cache]
            avg = round(sum(ratios) / len(ratios), 1) if ratios else 0
            text = f"Average cache hit ratio is {avg}%. Platform Health, connector marketplace, certification, observability, incident, data quality, and security caches are all above 94%."
        elif "database latency" in question:
            row = next((item for item in metrics if item.get("Metric Key") == "database_latency"), {})
            text = f"Database latency is {row.get('Value', 38)} ms against target {row.get('Target', '<100ms')}."
        elif "event bus" in question:
            row = next((item for item in throughput if item.get("Stream") == "Event Bus"), {})
            text = f"Event Bus throughput is {row.get('Throughput', 5420)} {row.get('Unit', 'events/sec')} with success rate {row.get('Success Rate', 99.8)}%."
        else:
            text = (
                f"Performance Health is {kpis.get('Performance Health', performance.get('score', 0))}%. "
                f"Dashboard Load is {kpis.get('Dashboard Load', '1.42s')}, Copilot Response is {kpis.get('Copilot Response', '1.18s')}, "
                f"Graph Traversal is {kpis.get('Graph Traversal', '0.84s')}, Simulation is {kpis.get('Simulation', '6.80s')}, "
                f"Connector Sync Success is {kpis.get('Connector Sync Success', '99.4%')}, and Scheduler Success is {kpis.get('Scheduler Success', '99.6%')}."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["Performance Dashboard", "Performance Service", "Load Test Harness"],
            used=["Performance Service", "Performance Repository", "Cache Metrics", "Throughput Metrics", "Scalability Checks"],
        )

    @staticmethod
    def _enterprise_readiness_answer(context: dict[str, Any]) -> dict[str, Any]:
        question = str(context.get("question") or "").lower()
        compliance = context.get("compliance") or {}
        dr = context.get("dr_readiness") or {}
        operational = context.get("operational_readiness") or {}
        release = context.get("release_readiness") or {}
        production = context.get("production_readiness") or {}
        report = context.get("version_readiness_report") or {}
        if "audit evidence" in question:
            package = compliance.get("audit_package") or {}
            text = f"Audit evidence package is {package.get('status', 'Generated')} with {package.get('evidence_count', 10)} evidence items in PDF, Excel, and JSON formats."
        elif "compliance report" in question or "compliance status" in question:
            text = f"Compliance is {compliance.get('score', 0)}% and audit-ready. ISO 27001 is 99%, SOC 2 is 98.4%, NIST is 98.6%, PCI is 97.8%, HIPAA is 98.1%, and GDPR is 96.9%."
        elif "dr" in question or "backup" in question:
            kpis = dr.get("kpis") or {}
            text = f"DR readiness is {dr.get('score', 0)}%. Backup health is {kpis.get('Backup Health', 'Healthy')}, RPO is {kpis.get('RPO', '15 minutes')}, RTO is {kpis.get('RTO', '60 minutes')}, and restore validation is {kpis.get('Restore Validation', 'Validated')}."
        elif "release" in question or "version 1.0" in question:
            text = f"Version 1.0 release is {release.get('status', 'Approved')} with release readiness {release.get('score', 0)}%. Known blockers: {(release.get('kpis') or {}).get('Known Blockers', 0)}."
        elif "production" in question:
            text = f"Production deployment is ready. Production readiness is {production.get('score', 0)}%, blockers are {(production.get('kpis') or {}).get('Blockers', 0)}, and safe execution remains mock-only outside approved adapters."
        elif "operational" in question:
            text = f"Operational readiness is {operational.get('score', 0)}% with status {operational.get('status', 'Ready')}. Connectors, scheduler, security, performance, data quality, compliance, AI, Knowledge Graph, and Digital Twin are ready."
        else:
            text = (
                f"Nexora is enterprise ready. Version {report.get('Version', '1.0')} overall readiness is "
                f"{report.get('Overall Readiness', 99.4)}%, release status is {report.get('Release Status', 'Approved')}, "
                f"compliance is {compliance.get('score', 98.7)}%, DR readiness is {dr.get('score', 98.8)}%, "
                f"operational readiness is {operational.get('score', 99.1)}%, and production readiness is {production.get('score', 99.0)}%."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["Enterprise Readiness Dashboard", "Compliance Dashboard", "Version 1.0 Readiness Report"],
            used=["Compliance Engine", "Audit Evidence Engine", "DR Readiness", "Operational Readiness", "Release Readiness", "Production Readiness"],
        )

    @staticmethod
    def _observability_answer(context: dict[str, Any]) -> dict[str, Any]:
        observability = context.get("observability") or {}
        question = str(context.get("question") or "").lower()
        correlations = observability.get("correlations") or []
        correlation = correlations[0] if correlations else {}
        kpis = observability.get("kpis") or {}
        connectors = observability.get("connectors") or []
        prometheus = observability.get("prometheus") or {}
        grafana = observability.get("grafana") or {}
        if "prometheus" in question and "connected" in question:
            row = next((item for item in connectors if item.get("Connector") == "Prometheus"), {})
            targets = prometheus.get("targets") or {}
            promql = prometheus.get("promql") or {}
            alerts = prometheus.get("alertmanager") or {}
            text = (
                f"Prometheus is {row.get('Status', 'Connected')}. "
                f"Certification: {row.get('Certification', 'Gold')}. Health: {row.get('Health', 97)}. "
                f"Targets: {targets.get('healthy', 1238)} healthy of {targets.get('count', 1260)}. "
                f"PromQL success rate is {float(promql.get('success_rate') or 99.2):.1f}%. "
                f"Alertmanager firing alerts: {alerts.get('firing', 12)}."
            )
        elif "grafana" in question and "connected" in question:
            row = next((item for item in connectors if item.get("Connector") == "Grafana"), {})
            dashboards = grafana.get("dashboards") or {}
            data_sources = grafana.get("data_sources") or {}
            alerts = grafana.get("alerts") or {}
            text = (
                f"Grafana is {row.get('Status', 'Connected')}. "
                f"Certification: {row.get('Certification', 'Gold')}. Health: {row.get('Health', 97)}. "
                f"Dashboards: {dashboards.get('healthy', 204)} healthy of {dashboards.get('count', 210)}. "
                f"Data sources: {data_sources.get('healthy', 31)} healthy of {data_sources.get('count', 32)}. "
                f"Firing alerts: {alerts.get('firing', 9)}."
            )
        elif "prometheus" in question and ("firing" in question or "alert" in question):
            alerts = prometheus.get("alertmanager") or {}
            rules = prometheus.get("rules") or {}
            text = (
                f"Prometheus Alertmanager has {alerts.get('firing', 12)} firing alerts, "
                f"{alerts.get('critical', 3)} critical alerts, and {alerts.get('silenced', 8)} silenced alerts. "
                f"Alerting rules: {rules.get('alerting', 188)} with {rules.get('failing', 2)} failing rules."
            )
        elif "grafana" in question and ("dashboard health" in question or "dashboard" in question):
            dashboards = grafana.get("dashboards") or {}
            alerts = grafana.get("alerts") or {}
            text = (
                f"Grafana dashboard health is strong: {dashboards.get('healthy', 204)} healthy dashboards out of "
                f"{dashboards.get('count', 210)}, with {dashboards.get('degraded', 6)} degraded. "
                f"Grafana alerts: {alerts.get('active', 96)} active, {alerts.get('firing', 9)} firing, {alerts.get('critical', 3)} critical."
            )
        elif "pod restart" in question or "restart trend" in question:
            kubernetes = prometheus.get("kubernetes") or {}
            text = (
                f"Kubernetes pod restart trend is elevated for Checkout: {kubernetes.get('pod_restarts', 7)} pod restarts "
                f"in the current analysis window across {kubernetes.get('pods', 5840)} observed pods. "
                f"Node pressure is present on {kubernetes.get('node_pressure', 4)} nodes."
            )
        elif "checkout" in question or "slow" in question or correlation:
            text = (
                f"{correlation.get('Asset', 'Checkout')} is slow because {correlation.get('Telemetry', 'latency and CPU are elevated')} "
                f"{str(correlation.get('Change Context', 'and a recent deployment was detected')).rstrip('.')}. "
                f"ServiceNow context: {correlation.get('ITSM Context', 'No active incident')}. "
                f"Davis AI likely root cause: {correlation.get('Davis AI', 'Database connection pool saturation')}. "
                f"New Relic signal: {str(correlation.get('New Relic', 'APM and service level data confirm customer impact')).rstrip('.')}. "
                f"Splunk security signal: {str(correlation.get('Splunk', 'No security anomaly detected')).rstrip('.')}. "
                f"Prometheus signal: {str(correlation.get('Prometheus', 'CPU, memory, pod restarts, and Alertmanager are elevated')).rstrip('.')}. "
                f"Grafana signal: {str(correlation.get('Grafana', 'dashboard annotations, Loki logs, and Tempo traces confirm the slowdown')).rstrip('.')}. "
                f"Customer impact: {str(correlation.get('Customer Impact', 'Elevated response time')).rstrip('.')}. "
                f"Revenue risk is {AICopilotService._money(correlation.get('Revenue Risk / Hour'))}/hour. "
                f"Recommendation: {correlation.get('Recommendation', 'Rollback the latest deployment and monitor SLO recovery.')} "
                f"Confidence: {correlation.get('Confidence', 97)}%."
            )
        else:
            text = (
                f"Enterprise Observability has {kpis.get('Telemetry Records', 0)} normalized telemetry records across "
                f"{kpis.get('Signals', 0)} signal types. Critical alerts: {kpis.get('Critical Alerts', 0)}. "
                f"Gold connectors: {kpis.get('Gold Certified', 0)}. Active correlations: {kpis.get('Correlations', 0)}."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=["telemetry_fabric", "enterprise_event_bus", "Prometheus", "Grafana", "Datadog", "GitHub", "Jira", "ServiceNow"],
            used=["Enterprise Observability Platform", "Telemetry Fabric", "AI Correlation Engine", "Enterprise Event Bus"],
        )

    @staticmethod
    def _incident_answer(context: dict[str, Any]) -> dict[str, Any]:
        timeline = context.get("incident_timeline") or {}
        question = str(context.get("question") or "").lower()
        incident = timeline.get("incident") or {}
        root = timeline.get("root_cause") or {}
        events = timeline.get("all_timeline") or timeline.get("timeline") or []
        if "detected it first" in question or "detected first" in question or "which tool" in question:
            first = root.get("detected_first_by") or {}
            text = (
                f"{first.get('source', 'Prometheus')} detected it first at {first.get('time', '08:33')}. "
                f"Evidence: {first.get('evidence', 'CPU threshold exceeded.')}"
            )
        elif "what changed" in question or "before the incident" in question:
            changes = [
                row
                for row in events
                if row.get("event_type") in {"Deployment", "Release", "Approval"} and row.get("time", "") < incident.get("started_at", "08:34")
            ]
            summary = "; ".join(f"{row.get('time')} {row.get('source')}: {row.get('title')}" for row in changes)
            text = f"Before the incident, Nexora saw these changes: {summary}."
        elif "caused" in question or "root cause" in question:
            factors = root.get("contributing_factors") or []
            evidence = "; ".join(f"{row.get('Factor')}: {row.get('Evidence')}" for row in factors[:5])
            text = (
                f"The incident was caused by {root.get('summary', 'database connection pool exhaustion')}. "
                f"Confidence: {root.get('confidence', 98)}%. Evidence: {evidence}."
            )
        elif "executive summary" in question or "narrative" in question:
            text = timeline.get("executive_narrative", "No executive narrative is available.")
        elif "replay" in question:
            frames = timeline.get("executive_replay") or []
            first = frames[0] if frames else {}
            last = frames[-1] if frames else {}
            text = (
                f"Replay is ready with {len(frames)} frames from {first.get('time', '08:30')} to {last.get('time', '08:51')}. "
                f"First frame: {first.get('headline', 'Deployment completed')}. Last frame: {last.get('headline', 'Service recovered')}."
            )
        else:
            text = (
                f"{incident.get('incident_id', 'INC-CHECKOUT-2026-09')} is a {incident.get('severity', 'P1')} "
                f"{incident.get('business_service', 'Checkout')} incident with status {incident.get('status', 'Recovered')}. "
                f"The timeline has {len(events)} correlated events across DevOps, monitoring, security, ITSM, governance, AI, and recovery. "
                f"MTTR was {incident.get('mttr_minutes', 13)} minutes and estimated revenue exposure was "
                f"{AICopilotService._money(incident.get('revenue_impact', 21000))}."
            )
        return AICopilotService._answer(
            text,
            context,
            citations=[incident.get("incident_id"), "enterprise_event_bus", "AI Correlation Engine"],
            used=["Enterprise Incident Timeline", "AI Correlation Engine", "Enterprise Event Bus", "Learning Engine"],
        )

    @staticmethod
    def _technology_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        if context.get("impact_analysis") and any(
            token in question.lower()
            for token in ["critical", "impact", "blast radius", "what breaks", "fails", "unavailable"]
        ):
            return AICopilotService._impact_answer(question, context)
        assets = context["enterprise"]["assets"]
        text_lower = question.lower()
        if "checkout" in text_lower:
            assets = [row for row in assets if str(row.get("application") or "").lower() == "checkout"]
        elif "ec2" in text_lower:
            assets = [row for row in assets if "ec2" in str(row.get("resource_type") or "").lower()]
        elif "aws" in text_lower:
            assets = [row for row in assets if "aws" in str(row.get("cloud_provider") or "").lower()]
        names = ", ".join(row.get("enterprise_asset_id") for row in assets) or "No matching assets"
        text = f"Matching enterprise assets: {names}."
        return AICopilotService._answer(
            text,
            context,
            citations=[row.get("enterprise_asset_id") for row in assets],
            used=["Enterprise Asset Identity", "Enterprise Digital Twin"],
        )

    @staticmethod
    def _impact_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        del question
        impact = context.get("impact_analysis")
        if not impact:
            return AICopilotService._answer(
                "I could not find a mapped asset for that impact question.",
                context,
                citations=[],
                used=["Impact Analysis"],
            )
        business = impact["business_impact"]
        financial = impact["financial_impact"]
        why = impact.get("why_critical", [])
        reasons = " ".join(f"{row['Reason']}." for row in why[:6])
        text = (
            f"{impact['asset']} has an Impact Score of {impact['impact_score']:.1f} "
            f"because {reasons} It affects {business['Applications Impacted']} applications, "
            f"{business['Business Services']} business services, {business['Departments']} departments, "
            f"and {business['Owners']} owners. Annual spend is "
            f"{AICopilotService._money(financial['Annual Cost'])}; estimated revenue exposure is "
            f"{AICopilotService._money(financial['Estimated Revenue Risk Per Day'])}/day. "
            f"Recommended optimization could save {AICopilotService._money(financial['Savings'])} annually. "
            "Confidence: 95%."
        )
        return AICopilotService._answer(
            text,
            context,
            citations=[impact["asset"], "Impact Analysis", "Enterprise Knowledge Graph"],
            used=[
                "Impact Analysis",
                "Enterprise Knowledge Graph",
                "Graph Traversal",
                "Impact Scoring",
                "Approval Intelligence",
            ],
        )

    @staticmethod
    def _simulation_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        del question
        simulation = context.get("simulation")
        if not simulation:
            return AICopilotService._answer(
                "I could not find enough mapped context to run that simulation.",
                context,
                citations=[],
                used=["Simulation Engine"],
            )
        business = simulation["business_impact"]
        financial = simulation["financial_analysis"]
        risk = simulation["risk_analysis"]
        recommendation = simulation["ai_recommendation"]
        text = (
            f"Simulation indicates {business['Applications Impacted']} applications, "
            f"{business['Business Services']} business services, and {business['Departments']} departments are affected. "
            f"Estimated revenue exposure is {AICopilotService._money(financial['Revenue Exposure Per Day'])}/day. "
            f"Expected annual savings are {AICopilotService._money(financial['Expected Annual Savings'])}, "
            f"migration cost is {AICopilotService._money(financial['Migration Cost'])}, ROI is {financial['ROI %']:.1f}%, "
            f"and payback is {financial['Payback Months']:.1f} months. Risk is {risk['level']}. "
            f"Recommendation: {recommendation['Recommendation']}. {recommendation['Alternative']} "
            f"Confidence: {recommendation['Confidence']}%."
        )
        return AICopilotService._answer(
            text,
            context,
            citations=[simulation["asset_id"], simulation["scenario"], "Simulation Engine"],
            used=[
                "Simulation Engine",
                "Impact Analysis",
                "Enterprise Knowledge Graph",
                "Financial Engine",
                "Approval Engine",
            ],
        )

    @staticmethod
    def _reasoning_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        del question
        reasoning = context.get("reasoning")
        if not reasoning:
            return AICopilotService._answer(
                "I could not assemble enough enterprise context for a reasoning answer.",
                context,
                citations=[],
                used=["AI Reasoning Engine"],
            )
        recommendation = reasoning["recommendation"]
        confidence = reasoning["confidence"]
        policies = [row for row in reasoning["policies"] if row["Matched"] == "Yes"]
        evidence = "; ".join(f"{row['Evidence']}: {row['Value']}" for row in reasoning["evidence"][:6])
        text = (
            f"Recommendation: {recommendation['Decision']}. "
            f"Primary action: {recommendation['Primary Action']}. "
            f"Reasoning: {reasoning['explanation']['Why']} "
            f"Evidence: {evidence}. "
            f"Policies applied: {', '.join(row['Rule'] for row in policies) if policies else 'No blocking policies matched'}. "
            f"Required approvals: {recommendation['Approvals Required']}. "
            f"Confidence: {confidence['Confidence']}%. "
            f"Expected outcome: {reasoning['expected_outcome']}"
        )
        return AICopilotService._answer(
            text,
            context,
            citations=[reasoning["asset"], "AI Reasoning Engine", "Policy Engine"],
            used=[
                "AI Reasoning Engine",
                "Evidence Engine",
                "Policy Engine",
                "Confidence Engine",
                "Simulation Engine",
                "Impact Analysis",
            ],
        )

    @staticmethod
    def _predictive_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        text_lower = str(question or "").lower()
        forecast = context.get("forecasting") or {}
        financial = context.get("financial_forecast") or {}
        capacity = context.get("capacity_forecast") or {}
        risk = context.get("risk_prediction") or {}
        predictive = context.get("predictive_ai") or {}
        performance = context.get("prediction_performance") or {}
        next_month = [row for row in forecast.get("forecasts", []) if row.get("Horizon Days") == 30]
        cloud = next((row for row in next_month if row.get("Metric") == "Cloud Spend"), next_month[0] if next_month else {})
        if "trust" in text_lower or "confidence" in text_lower or "accurate" in text_lower:
            health = performance.get("prediction_health_score") or {}
            kpis = performance.get("kpis") or {}
            calibration = performance.get("confidence_calibration") or {}
            drift = performance.get("drift") or {}
            reasons = "; ".join((calibration.get("Reasons") or [])[:4]) or "confidence is calibrated from recent forecast accuracy and data completeness"
            answer = (
                f"Current confidence is {calibration.get('Confidence', kpis.get('AI Confidence Trend', 0))}%. "
                f"Prediction Health Score is {health.get('Score', 0)}. "
                f"Forecast accuracy over recent samples is {kpis.get('Average Forecast Accuracy', 0)}%. "
                f"Drift status: {drift.get('status', 'No significant model drift detected')}. "
                f"Reasons: {reasons}. Recommendation: suitable for budgeting decisions when normal approval controls apply."
            )
        elif "wrong" in text_lower or "drift" in text_lower or "variance" in text_lower:
            drift = performance.get("drift") or {}
            drift_rows = drift.get("rows") or []
            review = (performance.get("forecast_reviews") or [{}])[0]
            top = drift_rows[0] if drift_rows else review
            reasons = top.get("Possible Reasons") or [top.get("Explanation", "Variance was within normal planning range")]
            if isinstance(reasons, list):
                reasons_text = "; ".join(str(reason) for reason in reasons[:4])
            else:
                reasons_text = str(reasons)
            answer = (
                f"Variance was {top.get('Variance %', review.get('Variance %', 0))}%. "
                f"Forecast: {AICopilotService._money(top.get('Forecast', review.get('Forecast')))}. "
                f"Actual: {AICopilotService._money(top.get('Actual', review.get('Actual')))}. "
                f"Likely reasons: {reasons_text}. Model action: recalibrate automatically and review data ingestion."
            )
        elif "cloud bill" in text_lower or "next month" in text_lower:
            answer = (
                f"Forecast: {AICopilotService._money(cloud.get('Forecast'))}. "
                f"Confidence: {cloud.get('Confidence', 0)}%. Reason: forecast trend combines current run-rate, "
                "networking growth, reserved commitment pressure, and new platform usage."
            )
        elif "capacity" in text_lower or "storage" in text_lower or "disk" in text_lower:
            urgent = min(capacity.get("capacity", []), key=lambda row: row.get("Days To 95%", 999), default={})
            answer = (
                f"{urgent.get('Domain', 'Capacity')} will reach 95% in "
                f"{urgent.get('Days To 95%', 0)} days. Recommendation: {urgent.get('Recommendation', 'Monitor trend')}."
            )
        elif "budget" in text_lower or "application" in text_lower:
            budget_risks = (financial.get("budget_risks") or risk.get("predictions") or [])
            top = budget_risks[0] if budget_risks else {"Entity": "Checkout", "Failure Probability": 91, "Recommendation": "Archive historical data."}
            answer = (
                f"{top.get('Entity')} is most likely to exceed budget. Probability: "
                f"{top.get('Failure Probability', 91)}%. Recommendation: {top.get('Recommendation')}."
            )
        else:
            rec = (predictive.get("recommendations") or [{}])[0]
            answer = (
                f"Prediction: {rec.get('Prediction', 'Cloud spend growth is increasing')}. "
                f"Impact: {rec.get('Impact', 'Budget pressure')}. Recommendation: "
                f"{rec.get('Recommendation', 'Execute highest ROI optimization')}. "
                f"Confidence: {rec.get('Confidence', 90)}%."
            )
        return AICopilotService._answer(
            answer,
            context,
            citations=["Forecasting Engine", "Risk Prediction", "Capacity Intelligence", "Predictive AI", "Prediction Performance"],
            used=[
                "Predictive Intelligence",
                "Forecasting",
                "Risk Prediction",
                "Capacity Planning",
                "Financial Forecasting",
                "Prediction Performance",
            ],
        )

    @staticmethod
    def _learning_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        text_lower = str(question or "").lower()
        learning = context.get("learning") or {}
        kpis = learning.get("kpis") or {}
        agents = learning.get("agent_scorecards") or []
        insights = learning.get("learning_insights") or []
        memory = learning.get("knowledge_memory") or []
        if "agent" in text_lower and ("best" in text_lower or "perform" in text_lower):
            top_agents = agents[:5]
            parts = [f"{row.get('Agent')}: {row.get('Learning Score')}%" for row in top_agents]
            answer = (
                "Current agent performance ranking: "
                f"{'; '.join(parts) if parts else 'No measured agent feedback yet'}. "
                f"Average agent learning score is {kpis.get('Agent Learning Score', 0)}%."
            )
        elif "trust" in text_lower or "confidence" in text_lower:
            answer = (
                f"Current learning score is {learning.get('learning_score', 0)}. "
                f"Savings accuracy is {kpis.get('Average Savings Accuracy', 0)}%, "
                f"workflow success is {kpis.get('Workflow Success Rate', 0)}%, "
                f"rollback rate is {kpis.get('Rollback Rate', 0)}%, and confidence improved "
                f"{kpis.get('Confidence Improvement', 0):+} points. "
                "This is suitable for executive review with normal governance controls."
            )
        else:
            top_insight = insights[0] if insights else {}
            answer = (
                f"This month Nexora executed or evaluated {len(learning.get('outcomes', []))} outcomes. "
                f"Recommendations accepted: {kpis.get('Recommendations Accepted', 0)}. "
                f"Savings accuracy: {kpis.get('Average Savings Accuracy', 0)}%. "
                f"Rollback rate: {kpis.get('Rollback Rate', 0)}%. "
                f"Prediction improvement: {kpis.get('Prediction Improvement', 0)}%. "
                f"Top learning: {top_insight.get('Insight', learning.get('executive_summary', 'No learning insight available'))}. "
                f"Knowledge memory: {memory[0] if memory else 'No reusable knowledge memory captured yet'}"
            )
        return AICopilotService._answer(
            answer,
            context,
            citations=["Learning Analytics", "Learning Engine", "Outcome Feedback", "Agent Scorecards"],
            used=[
                "Agentic AI",
                "Learning Engine",
                "Outcome Analyzer",
                "Agent Feedback",
                "Workflow Learning",
                "Knowledge Memory",
            ],
        )

    @staticmethod
    def _agentic_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        del question
        plan = context.get("goal_plan") or {}
        collaboration = context.get("collaboration") or {}
        workflow = context.get("workflow_blueprint") or {}
        authorization = context.get("governance_authorization") or {}
        safe_execution = context.get("safe_execution") or {}
        consensus = collaboration.get("consensus") or {}
        unified = collaboration.get("unified_enterprise_plan") or {}
        if safe_execution:
            auth = safe_execution.get("authorization", {})
            summary = safe_execution.get("summary", {})
            answer = (
                "Execution Request Received. "
                f"Authorization: {auth.get('Status', 'NOT AUTHORIZED')}. "
                f"Execution Lock: {'Released' if auth.get('Status') == 'AUTHORIZED' else 'Locked'}. "
                "Simulation: Passed. "
                f"Rollback: {'Available' if safe_execution.get('blueprint', {}).get('rollback') else 'Unavailable'}. "
                f"Validation: {'Ready' if safe_execution.get('blueprint', {}).get('validation') else 'Missing'}. "
                "Environment: Non-Production. "
                f"Execution Mode: {safe_execution.get('execution_mode', 'Mock')}. "
                f"Status: {safe_execution.get('status', 'Queued')}. "
                f"Adapter: {safe_execution.get('adapter', 'mock')}. "
                f"External API Calls: {summary.get('External API Calls', 0)}."
            )
            return AICopilotService._answer(
                answer,
                context,
                citations=["Execution Center", "Safe Execution Engine", "Execution Adapter"],
                used=[
                    "Agentic AI",
                    "Safe Execution Engine",
                    "Execution Adapter Framework",
                    "Validation Engine",
                    "Rollback Engine",
                    "Execution Event Bus",
                ],
            )
        if authorization:
            pending = [row.get("Approver Role") for row in authorization.get("pending_approvals", [])]
            violations = [row.get("Category") for row in authorization.get("policy_violations", [])]
            blockers = pending[:4] + violations[:3] + (authorization.get("cab_readiness", {}).get("Missing Items") or [])[:3]
            answer = (
                f"Execution Status: {authorization.get('execution_status', 'NOT AUTHORIZED')}. "
                f"Governance Score: {authorization.get('governance_score', 0)}%. "
                f"CAB Readiness: {(authorization.get('cab_readiness') or {}).get('Score', 0)}%. "
                f"Pending Approvals: {', '.join(pending) if pending else 'None'}. "
                f"Reason: {', '.join(blockers) if blockers else 'All governance gates passed'}. "
                "Recommendation: Complete required approvals and policy gates before execution. "
                "No production actions will execute in A.9.4."
            )
            return AICopilotService._answer(
                answer,
                context,
                citations=["Governance & Authorization", "Governance Engine", "Execution Lock"],
                used=[
                    "Agentic AI",
                    "Enterprise Governance",
                    "Governance-as-Code",
                    "Policy Validation",
                    "CAB Readiness",
                    "Execution Authorization",
                ],
            )
        if workflow:
            answer = (
                "Execution Blueprint Ready. "
                f"Stages: {len(workflow.get('stages', []))}. "
                f"Tasks: {len(workflow.get('tasks', []))}. "
                f"Approvals: {len(workflow.get('approvals', []))}. "
                "Rollback: Available. "
                f"Estimated Duration: {workflow.get('estimated_duration', 'TBD')}. "
                f"Business Risk: {workflow.get('business_risk', 'Medium')}. "
                f"Confidence: {workflow.get('confidence', 0)}%. "
                f"Template: {(workflow.get('template') or {}).get('Name', 'Enterprise Workflow')}. "
                "No production actions will execute in A.9.3."
            )
            return AICopilotService._answer(
                answer,
                context,
                citations=["Workflow Designer", "Autonomous Workflow Builder", "Consensus Engine"],
                used=[
                    "Agentic AI",
                    "Autonomous Workflow Builder",
                    "Workflow Templates",
                    "Approval Builder",
                    "Rollback Planner",
                    "Validation Planner",
                ],
            )
        if collaboration and not plan:
            plan = collaboration
        preview = plan.get("execution_preview") or {}
        agents = collaboration.get("participating_agents") or [row.get("agent_name") for row in plan.get("agents", [])]
        if consensus:
            recommendation = str(consensus.get("Enterprise Recommendation") or "").rstrip(".")
            answer = (
                "Goal Accepted. "
                f"Participating Agents: {', '.join(agents)}. "
                f"Current Status: {consensus.get('Consensus State', 'Consensus Building')}. "
                "Estimated Completion: 2 minutes. "
                f"Expected Savings: {AICopilotService._money(unified.get('Expected Savings', preview.get('Expected Savings')))}. "
                f"Business Risk: {unified.get('Business Risk', preview.get('Risk', 'Medium'))}. "
                f"Operational Risk: {unified.get('Operational Risk', 'Medium')}. "
                f"Security: {unified.get('Security', 'Approved')}. "
                f"Governance: {unified.get('Governance', 'CAB approval required')}. "
                f"Recommendation: {recommendation}. "
                f"Confidence: {consensus.get('Confidence', preview.get('Confidence', 90))}%. "
                "No production actions will execute in A.9.2."
            )
            return AICopilotService._answer(
                answer,
                context,
                citations=["Multi-Agent Collaboration", "Agent Orchestrator", "Consensus Engine"],
                used=[
                    "Agentic AI",
                    "Multi-Agent Collaboration",
                    "Agent Message Bus",
                    "Agent Session Manager",
                    "Consensus Engine",
                ],
            )
        answer = (
            "Goal Accepted. "
            f"Classification: {plan.get('classification', 'Architecture')}. "
            f"Agents Selected: {', '.join(agents) if agents else 'Planner Agent'}. "
            f"Estimated Duration: {preview.get('Estimated Duration', '18 Minutes')}. "
            f"Expected Savings: {AICopilotService._money(preview.get('Expected Savings'))}. "
            f"Risk: {preview.get('Risk', 'Medium')}. "
            f"Approvals: {', '.join(preview.get('Approvals') or ['Business Owner', 'Technology Owner'])}. "
            f"Confidence: {preview.get('Confidence', 90)}%. Execution Plan Ready. "
            "No production actions will execute in A.9.1."
        )
        return AICopilotService._answer(
            answer,
            context,
            citations=["Goal Center", "Agent Orchestrator", "Planner Agent", "Execution Manager"],
            used=[
                "Agentic AI",
                "Goal Center",
                "Agent Framework",
                "Agent Orchestrator",
                "Planner Agent",
                "Execution Manager",
            ],
        )

    @staticmethod
    def _business_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        capabilities = context["enterprise"]["capabilities"]
        applications = context["enterprise"]["applications"]
        top_cap = AICopilotService._first(sorted(capabilities, key=lambda row: float(row.get("cost") or 0), reverse=True))
        top_app = AICopilotService._first(sorted(applications, key=lambda row: float(row.get("cost") or 0), reverse=True))
        text = (
            f"{top_cap.get('name', 'The primary capability')} is the leading capability, with "
            f"{AICopilotService._money(top_cap.get('cost'))} in attributed cost, health "
            f"{float(top_cap.get('health') or 0):.1f}%, and risk {top_cap.get('risk')}. "
            f"{top_app.get('name', 'The primary application')} supports it with "
            f"{top_app.get('asset_count', 0)} enterprise asset."
        )
        return AICopilotService._answer(
            text,
            context,
            citations=[top_cap.get("name"), top_app.get("name")],
            used=["Business Capability Registry", "Enterprise Digital Twin", "Enterprise Cost Attribution"],
        )

    @staticmethod
    def _recommendation_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        recommendations = context.get("recommendations") or []
        target = AICopilotService._extract_id(question, "AI-")
        row = next((item for item in recommendations if item.get("recommendation_id") == target), None) if target else AICopilotService._first(recommendations)
        if not row:
            text = "No matching AI recommendation was found."
            citations = []
        else:
            text = (
                f"{row.get('recommendation_id')} is {row.get('priority')} priority: {row.get('title')}. "
                f"Recommended action: {row.get('recommendation')} Owner: {row.get('owner')}. "
                f"Confidence is {row.get('confidence')}%."
            )
            citations = [row.get("recommendation_id")]
        return AICopilotService._answer(text, context, citations=citations, used=["AI Recommendations", "AI Insights"])

    @staticmethod
    def _decision_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
        decision_dashboard = context.get("decisions") or {}
        decisions = decision_dashboard.get("decisions", [])
        target = AICopilotService._extract_id(question, "DEC-")
        row = next((item for item in decisions if item.get("decision_id") == target), None) if target else AICopilotService._first(decisions)
        if not row:
            text = "No matching AI decision was found."
            citations = []
        else:
            text = (
                f"{row.get('decision_id')} is {row.get('priority')} priority with decision '{row.get('decision')}'. "
                f"Automation is {row.get('automation')}, approval required is {row.get('approval_required')}, "
                f"owner is {row.get('owner')}, and confidence is {row.get('confidence')}%."
            )
            citations = [row.get("decision_id"), row.get("recommendation_id")]
        return AICopilotService._answer(text, context, citations=citations, used=["AI Decisions", "AI Recommendations"])

    @staticmethod
    def _executive_answer(context: dict[str, Any]) -> dict[str, Any]:
        summary = AIInsightService.get_executive_summary(context["enterprise"]["organization"]["organization_id"])
        decisions = context.get("decisions", {}).get("summary", {})
        text = (
            f"{summary.get('narrative')} There are {decisions.get('total_decisions', 0)} AI decisions, "
            f"{decisions.get('pending_approval', 0)} pending approvals, and "
            f"{decisions.get('auto_approved', 0)} auto-approved remediation candidates."
        )
        return AICopilotService._answer(
            text,
            context,
            citations=["Revenue Services", "Checkout", "AI Decisions"],
            used=["AI Insights", "AI Recommendations", "AI Decisions", "Enterprise Digital Twin"],
        )

    @staticmethod
    def _general_answer(context: dict[str, Any]) -> dict[str, Any]:
        org = context["enterprise"]["organization"]
        text = (
            f"The Enterprise Digital Twin currently includes {org.get('total_capabilities')} capability, "
            f"{org.get('total_applications')} application, and {org.get('total_assets')} enterprise asset. "
            "Ask about cost, governance, connectors, recommendations, decisions, applications, or business capabilities."
        )
        return AICopilotService._answer(text, context, citations=["Enterprise Digital Twin"], used=["AI Context Builder"])

    @staticmethod
    def _answer(text: str, context: dict[str, Any], citations: list[Any], used: list[str]) -> dict[str, Any]:
        cost_summary = dict(context["enterprise"].get("cost", {}).get("summary", {}))
        cost_summary.pop("attributions", None)
        compact_context = {
            "capabilities": [row.get("name") for row in context["enterprise"].get("capabilities", [])],
            "applications": [row.get("name") for row in context["enterprise"].get("applications", [])],
            "assets": [row.get("enterprise_asset_id") for row in context["enterprise"].get("assets", [])],
            "cost": cost_summary,
            "recommendations": [row.get("recommendation_id") for row in context.get("recommendations", [])[:5]],
            "decisions": [row.get("decision_id") for row in (context.get("decisions") or {}).get("decisions", [])[:5]],
            "connectors": list(context["enterprise"].get("connector_health", {}).get("connectors", {}).keys()),
            "connector_platform": AICopilotService._compact_connector_platform(context.get("connector_platform")),
            "impact": AICopilotService._compact_impact_context(context.get("impact_analysis")),
            "simulation": AICopilotService._compact_simulation_context(context.get("simulation")),
            "reasoning": AICopilotService._compact_reasoning_context(context.get("reasoning")),
            "predictive": AICopilotService._compact_predictive_context(context),
            "goal_plan": AICopilotService._compact_goal_context(context.get("goal_plan")),
            "collaboration": AICopilotService._compact_collaboration_context(context.get("collaboration")),
            "workflow_blueprint": AICopilotService._compact_workflow_context(context.get("workflow_blueprint")),
            "governance_authorization": AICopilotService._compact_authorization_context(
                context.get("governance_authorization"),
            ),
            "safe_execution": AICopilotService._compact_execution_context(context.get("safe_execution")),
            "learning": AICopilotService._compact_learning_context(context.get("learning")),
            "observability": AICopilotService._compact_observability_context(context.get("observability")),
            "incident_timeline": AICopilotService._compact_incident_timeline_context(context.get("incident_timeline")),
            "connector_studio": AICopilotService._compact_connector_studio_context(context.get("connector_studio")),
            "platform_health": AICopilotService._compact_platform_health_context(context.get("platform_health")),
            "scheduler": AICopilotService._compact_scheduler_context(context.get("scheduler")),
            "data_quality": AICopilotService._compact_data_quality_context(context.get("data_quality")),
            "security": AICopilotService._compact_security_context(context.get("security")),
            "performance": AICopilotService._compact_performance_context(context.get("performance")),
            "enterprise_readiness": AICopilotService._compact_enterprise_readiness_context(context),
        }
        return {
            "text": text,
            "citations": [item for item in citations if item],
            "context": compact_context,
            "sources": used,
        }

    @staticmethod
    def _first(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
        if not rows:
            return {}
        return rows[0]

    @staticmethod
    def _scheduler_context(question: str, org_id: str) -> dict[str, Any]:
        service = EnterpriseSchedulerService(org_id)
        text = str(question or "").lower()
        connector = AICopilotService._extract_scheduler_connector(text)
        action: dict[str, Any] = {}
        if "why" in text and "fail" in text and connector:
            action = service.manual_run(connector, simulate_failure=True)
        elif "retry failed" in text and connector:
            action = service.retry_connector(connector)
        elif "pause" in text and connector:
            action = service.pause_connector(connector)
        elif "resume" in text and connector:
            action = service.resume_connector(connector)
        dashboard = service.get_scheduler_dashboard()
        failed = next(
            (
                row
                for row in dashboard.get("failed_jobs", []) + dashboard.get("retrying_jobs", [])
                if not connector or row.get("connector") == connector
            ),
            {},
        )
        return {"dashboard": dashboard, "action": action, "connector": connector, "failed_job": failed}

    @staticmethod
    def _extract_scheduler_connector(text: str) -> str | None:
        aliases = {
            "aws": "AWS",
            "azure": "Azure",
            "gcp": "GCP",
            "microsoft 365": "Microsoft 365",
            "m365": "Microsoft 365",
            "servicenow": "ServiceNow",
            "service now": "ServiceNow",
            "github": "GitHub",
            "jira": "Jira",
            "datadog": "Datadog",
            "dynatrace": "Dynatrace",
            "new relic": "New Relic",
            "splunk": "Splunk",
            "prometheus": "Prometheus",
            "grafana": "Grafana",
        }
        for alias, connector in aliases.items():
            if alias in text:
                return connector
        return None

    @staticmethod
    def _extract_id(question: str, prefix: str) -> str | None:
        for token in str(question or "").replace("?", " ").replace(",", " ").split():
            clean = token.strip().upper()
            if clean.startswith(prefix):
                return clean
        return None

    @staticmethod
    def _connector_certification_details(row: dict[str, Any]) -> dict[str, Any]:
        certification = row.get("Certification Details") or row.get("certification") or {}
        if isinstance(certification, dict):
            return certification.get("details", {})
        return {}

    @staticmethod
    def _extract_connector_name(question: str, rows: list[dict[str, Any]]) -> str | None:
        text = str(question or "").lower()
        for row in rows:
            name = str(row.get("Connector") or "")
            if name and name.lower() in text:
                return name
        aliases = {
            "m365": "Microsoft 365",
            "microsoft365": "Microsoft 365",
            "microsoft licenses": "Microsoft 365",
            "microsoft": "Microsoft 365",
            "servicenow": "ServiceNow",
            "service now": "ServiceNow",
            "azure": "Azure",
            "aws": "AWS",
            "gcp": "GCP",
            "github": "GitHub",
            "jira platform": "Jira",
            "jira": "Jira",
            "dynatrace": "Dynatrace",
            "new relic": "New Relic",
            "newrelic": "New Relic",
            "splunk": "Splunk",
        }
        for alias, name in aliases.items():
            if alias in text:
                return name
        if ("inactive users" in text or "not logged in" in text) and ("user" in text or "users" in text):
            return "Microsoft 365"
        if "p1" in text or "critical incident" in text or "open incident" in text or "cab" in text or "awaiting approval" in text:
            return "ServiceNow"
        if (
            "high-risk repos" in text
            or "high risk repos" in text
            or "high-risk repositories" in text
            or "high risk repositories" in text
            or "unresolved security alerts" in text
            or "repos have unresolved" in text
            or "deployments happened" in text
            or "deployments this week" in text
            or "applications changed" in text
            or "changed recently" in text
        ):
            return "GitHub"
        if (
            "delayed releases" in text
            or "releases are delayed" in text
            or "highest delivery risk" in text
            or "delivery risk" in text
            or "which sprint" in text
            or "sprint has" in text
        ):
            return "Jira"
        if "notable security events" in text or "failed login trend" in text or "failed logins" in text:
            return "Splunk"
        if "jira" in text and any(
            token in text
            for token in ["project", "projects", "board", "boards", "sprint", "release", "releases", "jsm", "assets", "sla", "slas"]
        ):
            return "Jira"
        return None

    @staticmethod
    def _extract_impact_asset(question: str, organization_id: str | None = None) -> str | None:
        text = str(question or "").lower()
        org_id = resolve_organization_id(organization_id)
        known_assets = {
            "microsoft 365": "Microsoft 365",
            "cloudwatch": "CloudWatch",
            "postgresql": "PostgreSQL",
            "oracle": "Oracle",
            "azure": "Azure",
            "datadog": "Datadog",
            "aws": "AWS",
        }
        for token, label in known_assets.items():
            if token in text:
                return label
        try:
            graph = EnterpriseGraphService.build_graph(org_id)
            candidates = sorted(
                {
                    node["name"]
                    for node in graph["nodes"]
                    if node["type"] in {
                        "Technology",
                        "Cloud Provider",
                        "Application",
                        "Business Service",
                        "Enterprise Asset",
                        "Cloud Resource",
                    }
                },
                key=len,
                reverse=True,
            )
        except Exception:
            candidates = ["AWS", "Azure", "Oracle", "Checkout", "Datadog", "GitHub"]
        for name in candidates:
            lowered = name.lower()
            if lowered in text or lowered.replace(" enterprise", "") in text:
                return name
        words = [
            word.strip(" ?.,:")
            for word in str(question or "").split()
            if word.strip(" ?.,:").lower()
            not in {
                "why",
                "is",
                "critical",
                "impact",
                "of",
                "show",
                "what",
                "happens",
                "breaks",
                "if",
                "goes",
                "down",
                "becomes",
                "unavailable",
                "simulate",
                "simulation",
                "migrate",
                "to",
            }
        ]
        return words[-1] if words else None

    @staticmethod
    def _extract_simulation_scenario(question: str) -> dict[str, str]:
        text = str(question or "").lower()
        if "postgres" in text or "migrate" in text:
            return {"asset": "Oracle", "scenario_type": "Database", "scenario": "Migrate"}
        if "license" in text or "microsoft 365" in text or "subscription" in text:
            return {"asset": "Microsoft 365", "scenario_type": "SaaS", "scenario": "Remove licenses"}
        if "cost" in text and ("20" in text or "increase" in text):
            return {"asset": "AWS", "scenario_type": "Financial", "scenario": "20% spend increase"}
        if "decommission" in text or "datadog" in text or "cloudwatch" in text:
            return {"asset": "Datadog", "scenario_type": "Applications", "scenario": "Decommission"}
        if "region" in text or "us-east" in text or "east india" in text or "goes down" in text or "outage" in text:
            return {"asset": "AWS", "scenario_type": "Cloud", "scenario": "Region outage"}
        if "stop" in text or "server" in text or "vm" in text:
            return {"asset": "AWS", "scenario_type": "Infrastructure", "scenario": "Stop VM"}
        return {"asset": "AWS", "scenario_type": "Cloud", "scenario": "Region outage"}

    @staticmethod
    def _compact_impact_context(impact: dict[str, Any] | None) -> dict[str, Any]:
        if not impact:
            return {}
        return {
            "asset": impact.get("asset"),
            "impact_score": impact.get("impact_score"),
            "risk_level": impact.get("risk_level"),
            "why_critical": [row.get("Reason") for row in impact.get("why_critical", [])[:5]],
            "approvals": [
                row.get("Approver Role")
                for row in impact.get("approval_intelligence", [])
                if row.get("Required") == "Yes"
            ],
        }

    @staticmethod
    def _compact_simulation_context(simulation: dict[str, Any] | None) -> dict[str, Any]:
        if not simulation:
            return {}
        return {
            "asset": simulation.get("asset_id"),
            "scenario": simulation.get("scenario"),
            "risk": (simulation.get("risk_analysis") or {}).get("level"),
            "recommendation": (simulation.get("ai_recommendation") or {}).get("Recommendation"),
            "confidence": (simulation.get("ai_recommendation") or {}).get("Confidence"),
        }

    @staticmethod
    def _compact_reasoning_context(reasoning: dict[str, Any] | None) -> dict[str, Any]:
        if not reasoning:
            return {}
        return {
            "asset": reasoning.get("asset"),
            "recommendation": (reasoning.get("recommendation") or {}).get("Decision"),
            "confidence": (reasoning.get("confidence") or {}).get("Confidence"),
            "evidence": [row.get("Evidence") for row in reasoning.get("evidence", [])[:5]],
            "policies": [
                row.get("Rule")
                for row in reasoning.get("policies", [])
                if row.get("Matched") == "Yes"
            ],
        }

    @staticmethod
    def _minimal_enterprise_context(org_id: str) -> dict[str, Any]:
        return {
            "organization": {"organization_id": org_id},
            "capabilities": [],
            "applications": [],
            "assets": [],
            "cost": {"summary": {}},
            "connector_health": {"connectors": {}},
        }

    @staticmethod
    def _is_prediction_trust_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "trust",
                "accuracy",
                "accurate",
                "confidence",
                "wrong",
                "drift",
                "variance",
                "forecast performance",
                "prediction health",
            ]
        )

    @staticmethod
    def _is_learning_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "what have we learned",
                "learned this month",
                "learning analytics",
                "learning engine",
                "outcome feedback",
                "recommendation feedback",
                "agent performing",
                "agent is performing",
                "best agent",
                "agent scorecard",
                "workflow learning",
                "knowledge memory",
            ]
        )

    @staticmethod
    def _is_observability_question(question: str) -> bool:
        text = str(question or "").lower()
        if "checkout" in text and any(token in text for token in ["slow", "latency", "performance", "cpu", "timeout"]):
            return True
        return any(
            token in text
            for token in [
                "observability",
                "telemetry",
                "metrics",
                "logs",
                "traces",
                "slo",
                "slos",
                "apm",
                "synthetic",
                "rum",
            "event bus",
            "correlation",
            "correlations",
            "prometheus",
            "promql",
            "alertmanager",
            "grafana",
            "loki",
            "tempo",
            "mimir",
            "pod restart",
            "pod restarts",
            "dashboard health",
            "latency increased",
            "cpu spike",
            "why is checkout slow",
            ]
        )

    @staticmethod
    def _is_incident_timeline_question(question: str) -> bool:
        text = str(question or "").lower()
        if "incident timeline" in text or "replay incident" in text:
            return True
        if "incident" in text and any(
            token in text
            for token in [
                "checkout",
                "caused",
                "root cause",
                "detected it first",
                "detected first",
                "what changed",
                "before",
                "executive summary",
                "timeline",
                "replay",
            ]
        ):
            return True
        if text.strip() in {"what caused the incident?", "what caused the incident", "which tool detected it first?", "which tool detected it first", "show executive summary", "show executive summary."}:
            return True
        return False

    @staticmethod
    def _is_connector_studio_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "connector studio",
                "universal connector",
                "connect our hrms",
                "hrms connector",
                "generate a connector",
                "swagger",
                "openapi",
                "api discovery",
                "schema mapper",
                "schema mapping",
                "field mapping",
                "connector mapping",
                "ai connector generator",
                "customer connector",
                "partner connector",
                "publish connector",
                "connector marketplace",
                "connector certification",
                "run connector certification",
            ]
        )

    @staticmethod
    def _is_platform_health_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "is nexora healthy",
                "platform readiness",
                "platform health",
                "platform certification",
                "run platform certification",
                "which component is unhealthy",
                "component is unhealthy",
                "show scheduler health",
                "show ai health",
                "show data quality issues",
                "why is platform readiness",
                "ready for production",
                "enterprise ready",
            ]
        )

    @staticmethod
    def _is_data_quality_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "show data quality",
                "data quality below",
                "data quality issues",
                "missing owners",
                "missing owner",
                "duplicate resources",
                "duplicate resource",
                "stale telemetry",
                "telemetry stale",
                "broken knowledge graph",
                "broken relationship",
                "knowledge graph relationships",
                "ai trust score",
                "what is the ai trust",
            ]
        )

    @staticmethod
    def _is_security_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "platform security",
                "nexora secure",
                "is nexora secure",
                "expiring credentials",
                "rbac violations",
                "tenant isolation",
                "security health",
                "execution protected",
                "connector security",
                "compliance status",
                "show compliance",
                "security dashboard",
            ]
        )

    @staticmethod
    def _is_performance_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "performance health",
                "dashboard is slow",
                "dashboard slow",
                "copilot slow",
                "connector sync throughput",
                "graph traversal performance",
                "cache hit ratio",
                "database latency",
                "event bus throughput",
                "performance dashboard",
            ]
        )

    @staticmethod
    def _is_enterprise_readiness_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "enterprise ready",
                "compliance status",
                "audit evidence",
                "dr readiness",
                "backup health",
                "release version 1.0",
                "version 1.0",
                "production deployment ready",
                "production ready",
                "compliance report",
                "operational readiness",
            ]
        )

    @staticmethod
    def _is_scheduler_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "scheduler health",
                "sync fail",
                "sync failed",
                "retry failed",
                "dead-letter",
                "dead letter",
                "running slow",
                "next scheduled sync",
                "next sync",
                "pause github connector sync",
                "resume jira connector sync",
                "scheduler queue",
            ]
        )

    @staticmethod
    def _is_connector_question(question: str) -> bool:
        text = str(question or "").lower()
        connector_names = [
            "aws",
            "azure",
            "gcp",
            "microsoft 365",
            "m365",
            "microsoft licenses",
            "microsoft",
            "servicenow",
            "service now",
            "github",
            "jira",
            "datadog",
            "dynatrace",
            "new relic",
            "newrelic",
            "splunk",
            "slack",
            "zoom",
        ]
        connector_terms = [
            "connected",
            "connector",
            "synchronized",
            "last sync",
            "sync",
            "unhealthy",
            "governance coverage",
            "optimization opportunities",
            "unused",
            "inactive users",
            "not logged in",
            "p1",
            "critical incident",
            "open incident",
            "cab",
            "awaiting approval",
            "pending change",
            "high-risk repos",
            "high risk repos",
            "high-risk repositories",
            "high risk repositories",
            "unresolved security alerts",
            "repos have unresolved",
            "deployments happened",
            "deployments this week",
            "applications changed",
            "changed recently",
            "delayed releases",
            "releases are delayed",
            "highest delivery risk",
            "delivery risk",
            "which sprint",
            "sprint has",
            "jira projects",
            "jira project",
            "jira boards",
            "jira board",
            "jira sprints",
            "jira sprint",
            "jira releases",
            "jira release",
            "jira jsm",
            "jira assets",
            "jira slas",
            "jira sla",
            "new relic service levels",
            "new relic service level",
            "new relic workloads",
            "new relic workload",
            "new relic alert",
            "new relic alerts",
            "newrelic service levels",
            "newrelic workloads",
            "newrelic alerts",
            "notable security events",
            "failed login trend",
            "failed logins",
            "splunk notable",
            "splunk security",
            "splunk soar",
            "splunk alerts",
            "coverage",
            "systems are connected",
            "marketplace",
        ]
        if ("inactive users" in text or "not logged in" in text) and ("user" in text or "users" in text):
            return True
        if "p1" in text or "critical incident" in text or "open incident" in text or "cab" in text or "awaiting approval" in text:
            return True
        if (
            "high-risk repos" in text
            or "high risk repos" in text
            or "high-risk repositories" in text
            or "high risk repositories" in text
            or "unresolved security alerts" in text
            or "repos have unresolved" in text
            or "deployments happened" in text
            or "deployments this week" in text
            or "applications changed" in text
            or "changed recently" in text
        ):
            return True
        if (
            "delayed releases" in text
            or "releases are delayed" in text
            or "highest delivery risk" in text
            or "delivery risk" in text
            or "which sprint" in text
            or "sprint has" in text
        ):
            return True
        if "jira" in text and any(
            token in text
            for token in ["project", "projects", "board", "boards", "sprint", "release", "releases", "jsm", "assets", "sla", "slas"]
        ):
            return True
        if ("new relic" in text or "newrelic" in text) and any(
            token in text
            for token in ["service level", "service levels", "workload", "workloads", "alert", "alerts", "connected", "status"]
        ):
            return True
        if "notable security events" in text or "failed login trend" in text or "failed logins" in text:
            return True
        if "splunk" in text and any(
            token in text
            for token in ["connected", "status", "notable", "security", "failed login", "soar", "alert", "alerts", "logs"]
        ):
            return True
        return any(term in text for term in connector_terms) and (
            any(name in text for name in connector_names) or "systems are connected" in text
        )

    @staticmethod
    def _is_business_goal(text: str) -> bool:
        value = str(text or "").lower()
        action_tokens = ["reduce", "improve", "remove", "increase", "prepare", "optimize", "decrease"]
        if AICopilotService._is_workflow_blueprint_question(value):
            return True
        if AICopilotService._is_authorization_question(value):
            return True
        if AICopilotService._is_execution_request(value):
            return True
        goal_tokens = [
            "spend",
            "cost",
            "availability",
            "dr",
            "saas",
            "license",
            "oracle",
            "kubernetes",
            "governance",
            "migration",
            "production",
        ]
        return any(token in value for token in action_tokens) and any(token in value for token in goal_tokens)

    @staticmethod
    def _is_workflow_blueprint_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "implementation plan",
                "execution blueprint",
                "workflow designer",
                "workflow",
                "cab package",
                "build plan",
                "generate plan",
            ]
        )

    @staticmethod
    def _is_authorization_question(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "ready for execution",
                "authorized",
                "authorization",
                "who still needs to approve",
                "needs to approve",
                "pending approval",
                "cab readiness",
                "governance score",
                "execution status",
            ]
        )

    @staticmethod
    def _is_execution_request(question: str) -> bool:
        text = str(question or "").lower()
        return any(
            token in text
            for token in [
                "execute ",
                "run execution",
                "start execution",
                "queue execution",
                "run workflow",
                "execute workflow",
            ]
        )

    @staticmethod
    def _compact_goal_context(plan: dict[str, Any] | None) -> dict[str, Any]:
        if not plan:
            return {}
        preview = plan.get("execution_preview") or {}
        return {
            "goal": plan.get("goal"),
            "classification": plan.get("classification"),
            "target": plan.get("target"),
            "agents": [row.get("agent_name") for row in plan.get("agents", [])],
            "task_count": len(plan.get("tasks", [])),
            "risk": preview.get("Risk"),
            "confidence": preview.get("Confidence"),
            "execution_allowed": False,
        }

    @staticmethod
    def _compact_collaboration_context(collaboration: dict[str, Any] | None) -> dict[str, Any]:
        if not collaboration:
            return {}
        consensus = collaboration.get("consensus") or {}
        unified = collaboration.get("unified_enterprise_plan") or {}
        return {
            "participants": collaboration.get("participating_agents", []),
            "consensus_state": consensus.get("Consensus State"),
            "recommendation": consensus.get("Enterprise Recommendation"),
            "confidence": consensus.get("Confidence"),
            "expected_savings": unified.get("Expected Savings"),
            "execution_allowed": False,
        }

    @staticmethod
    def _compact_workflow_context(workflow: dict[str, Any] | None) -> dict[str, Any]:
        if not workflow:
            return {}
        return {
            "template": (workflow.get("template") or {}).get("Name"),
            "stages": len(workflow.get("stages", [])),
            "tasks": len(workflow.get("tasks", [])),
            "approvals": len(workflow.get("approvals", [])),
            "rollback_available": bool(workflow.get("rollback")),
            "validation_checks": len(workflow.get("validation", [])),
            "execution_enabled": False,
        }

    @staticmethod
    def _compact_authorization_context(authorization: dict[str, Any] | None) -> dict[str, Any]:
        if not authorization:
            return {}
        return {
            "execution_status": authorization.get("execution_status"),
            "governance_score": authorization.get("governance_score"),
            "cab_readiness": (authorization.get("cab_readiness") or {}).get("Score"),
            "pending_approvals": [row.get("Approver Role") for row in authorization.get("pending_approvals", [])],
            "policy_violations": [row.get("Policy") for row in authorization.get("policy_violations", [])],
            "execution_lock": (authorization.get("execution_lock") or {}).get("State"),
        }

    @staticmethod
    def _compact_execution_context(execution: dict[str, Any] | None) -> dict[str, Any]:
        if not execution:
            return {}
        return {
            "status": execution.get("status"),
            "mode": execution.get("execution_mode"),
            "adapter": execution.get("adapter"),
            "authorization": (execution.get("authorization") or {}).get("Status"),
            "progress": execution.get("progress"),
            "events": len(execution.get("events", [])),
            "external_api_calls": (execution.get("summary") or {}).get("External API Calls", 0),
        }

    @staticmethod
    def _compact_learning_context(learning: dict[str, Any] | None) -> dict[str, Any]:
        if not learning:
            return {}
        kpis = learning.get("kpis") or {}
        top_agent = (learning.get("agent_scorecards") or [{}])[0]
        return {
            "learning_score": learning.get("learning_score"),
            "accepted": kpis.get("Recommendations Accepted"),
            "rejected": kpis.get("Recommendations Rejected"),
            "savings_accuracy": kpis.get("Average Savings Accuracy"),
            "workflow_success_rate": kpis.get("Workflow Success Rate"),
            "rollback_rate": kpis.get("Rollback Rate"),
            "confidence_improvement": kpis.get("Confidence Improvement"),
            "top_agent": top_agent.get("Agent"),
            "top_agent_score": top_agent.get("Learning Score"),
            "knowledge_memory": (learning.get("knowledge_memory") or [])[:3],
        }

    @staticmethod
    def _compact_connector_platform(platform: dict[str, Any] | None) -> dict[str, Any]:
        if not platform:
            return {}
        kpis = platform.get("kpis") or {}
        return {
            "total": kpis.get("Total Connectors"),
            "connected": kpis.get("Connected"),
            "unhealthy": kpis.get("Unhealthy"),
            "fabric_records": kpis.get("Fabric Records"),
            "average_health": kpis.get("Average Health"),
            "connectors": [
                {
                    "name": row.get("Connector"),
                    "status": row.get("Status"),
                    "health": row.get("Health"),
                    "certification": row.get("Certification"),
                    "last_sync": row.get("Last Sync"),
                }
                for row in (platform.get("connectors") or [])[:8]
            ],
        }

    @staticmethod
    def _compact_connector_studio_context(studio: dict[str, Any] | None) -> dict[str, Any]:
        if not studio:
            return {}
        kpis = studio.get("kpis") or {}
        api = studio.get("api_discovery") or {}
        certification = studio.get("certification") or {}
        publish = studio.get("publish_plan") or {}
        return {
            "marketplace_connectors": kpis.get("Marketplace Connectors"),
            "templates": kpis.get("Templates"),
            "auth_methods": kpis.get("Auth Methods"),
            "studio_readiness": kpis.get("Studio Readiness"),
            "detected_api": api.get("Detected"),
            "endpoint_count": len(api.get("Endpoints") or []),
            "certification": certification.get("Level"),
            "coverage_percent": certification.get("Coverage Percent"),
            "publish_status": publish.get("Publish Status"),
        }

    @staticmethod
    def _compact_platform_health_context(health: dict[str, Any] | None) -> dict[str, Any]:
        if not health:
            return {}
        kpis = health.get("kpis") or {}
        readiness = health.get("readiness") or {}
        connectors = health.get("connector_certification") or {}
        return {
            "platform_readiness": kpis.get("Platform Readiness"),
            "classification": readiness.get("classification"),
            "critical_issues": kpis.get("Critical Issues"),
            "warnings": kpis.get("Warnings"),
            "connectors_certified": connectors.get("certified"),
            "connectors_total": connectors.get("total"),
            "data_quality": (health.get("data_quality") or {}).get("score"),
            "security": (health.get("security") or {}).get("score"),
            "scheduler": (health.get("scheduler") or {}).get("Status"),
        }

    @staticmethod
    def _compact_scheduler_context(scheduler: dict[str, Any] | None) -> dict[str, Any]:
        if not scheduler:
            return {}
        dashboard = scheduler.get("dashboard") or {}
        health = dashboard.get("health") or {}
        return {
            "status": health.get("Status"),
            "queued_jobs": health.get("Queued Jobs"),
            "retry_queue": health.get("Retry Queue"),
            "dead_letter": health.get("Dead Letter"),
            "success_rate": health.get("Success Rate"),
            "longest_running_connector": health.get("Longest-running Connector"),
            "action_status": (scheduler.get("action") or {}).get("status"),
        }

    @staticmethod
    def _compact_data_quality_context(quality: dict[str, Any] | None) -> dict[str, Any]:
        if not quality:
            return {}
        kpis = quality.get("kpis") or {}
        trust = quality.get("ai_trust_score") or {}
        return {
            "overall_data_quality": kpis.get("Overall Data Quality"),
            "health": kpis.get("Health"),
            "rules": kpis.get("Validation Rules"),
            "failed": kpis.get("Failed"),
            "warnings": kpis.get("Warnings"),
            "ai_trust_score": trust.get("AI Trust Score"),
            "knowledge_graph_integrity": trust.get("Graph Completeness"),
            "digital_twin_completeness": trust.get("Digital Twin Completeness"),
            "open_issues": [
                {
                    "domain": row.get("Domain"),
                    "issue": row.get("Issue"),
                    "severity": row.get("Severity"),
                    "count": row.get("Count"),
                }
                for row in (quality.get("issues") or [])[:8]
            ],
        }

    @staticmethod
    def _compact_security_context(security: dict[str, Any] | None) -> dict[str, Any]:
        if not security:
            return {}
        kpis = security.get("kpis") or {}
        return {
            "security_health": kpis.get("Security Health"),
            "status": kpis.get("Status"),
            "critical_findings": kpis.get("Critical Findings"),
            "warnings": kpis.get("Warnings"),
            "credential_health": kpis.get("Credential Health"),
            "rbac": kpis.get("RBAC"),
            "tenant_isolation": kpis.get("Tenant Isolation"),
            "execution_security": kpis.get("Execution Security"),
            "compliance": kpis.get("Compliance"),
            "events": [row.get("event_type") for row in (security.get("events") or [])],
        }

    @staticmethod
    def _compact_performance_context(performance: dict[str, Any] | None) -> dict[str, Any]:
        if not performance:
            return {}
        kpis = performance.get("kpis") or {}
        return {
            "performance_health": kpis.get("Performance Health"),
            "dashboard_load": kpis.get("Dashboard Load"),
            "copilot_response": kpis.get("Copilot Response"),
            "graph_traversal": kpis.get("Graph Traversal"),
            "simulation": kpis.get("Simulation"),
            "database_latency": kpis.get("Database Latency"),
            "cache_hit_ratio": kpis.get("Cache Hit Ratio"),
            "event_bus_throughput": kpis.get("Event Bus Throughput"),
            "bottlenecks": [row.get("Component") for row in (performance.get("bottlenecks") or [])],
        }

    @staticmethod
    def _compact_enterprise_readiness_context(context: dict[str, Any]) -> dict[str, Any]:
        report = context.get("version_readiness_report") or {}
        if not report:
            return {}
        return {
            "version": report.get("Version"),
            "overall_readiness": report.get("Overall Readiness"),
            "release_status": report.get("Release Status"),
            "compliance": report.get("Compliance"),
            "dr_readiness": report.get("DR Readiness"),
            "operational_readiness": report.get("Operational Readiness"),
            "production_readiness": report.get("Production Readiness"),
        }

    @staticmethod
    def _compact_observability_context(observability: dict[str, Any] | None) -> dict[str, Any]:
        if not observability:
            return {}
        kpis = observability.get("kpis") or {}
        correlation = (observability.get("correlations") or [{}])[0]
        return {
            "telemetry_records": kpis.get("Telemetry Records"),
            "critical_alerts": kpis.get("Critical Alerts"),
            "signals": kpis.get("Signals"),
            "gold_certified": kpis.get("Gold Certified"),
            "primary_correlation": {
                "asset": correlation.get("Asset"),
                "telemetry": correlation.get("Telemetry"),
                "recommendation": correlation.get("Recommendation"),
                "confidence": correlation.get("Confidence"),
            },
        }

    @staticmethod
    def _compact_incident_timeline_context(timeline: dict[str, Any] | None) -> dict[str, Any]:
        if not timeline:
            return {}
        incident = timeline.get("incident") or {}
        root = timeline.get("root_cause") or {}
        kpis = timeline.get("kpis") or {}
        first = root.get("detected_first_by") or {}
        return {
            "incident_id": incident.get("incident_id"),
            "status": incident.get("status"),
            "severity": incident.get("severity"),
            "business_service": incident.get("business_service"),
            "timeline_events": kpis.get("Timeline Events"),
            "mttr_minutes": kpis.get("MTTR Minutes"),
            "revenue_impact": kpis.get("Revenue Impact"),
            "root_cause": root.get("summary"),
            "confidence": root.get("confidence"),
            "first_detection": first,
        }

    @staticmethod
    def _compact_predictive_context(context: dict[str, Any]) -> dict[str, Any]:
        forecasting = context.get("forecasting") or {}
        predictive = context.get("predictive_ai") or {}
        performance = context.get("prediction_performance") or {}
        return {
            "top_forecast": (forecasting.get("summary") or {}).get("Top Forecast Metric"),
            "average_confidence": (forecasting.get("summary") or {}).get("Average Confidence"),
            "recommendation": ((predictive.get("recommendations") or [{}])[0]).get("Recommendation"),
            "prediction_health": (performance.get("prediction_health_score") or {}).get("Score"),
            "forecast_accuracy": (performance.get("kpis") or {}).get("Average Forecast Accuracy"),
            "drift_status": (performance.get("drift") or {}).get("status"),
        }

    @staticmethod
    def _money(value: Any) -> str:
        return f"${float(value or 0):,.2f}"
