"""ACT-008 governed Ask Nexora boundary over certified PUE and enterprise services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from universal_evidence.interpretation import (
    DeterministicAnalyticalInterpreter,
    InterpretationPolicy,
    InterpretationStatus,
    NaturalLanguageQuestion,
    build_concept_catalog,
)
from universal_evidence.normalization.fingerprints import fingerprint
from universal_evidence.planning import AnalyticalIntentType


class AskState(str, Enum):
    SUPPORTED = "SUPPORTED"
    BLOCKED = "BLOCKED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT = "INSUFFICIENT"
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class GovernedAskResponse:
    state: AskState
    answer: str
    question: str
    question_class: str
    interpretation: Any | None
    plan: Any | None
    execution: Any | None
    citations: tuple[dict[str, Any], ...]
    provenance: tuple[dict[str, Any], ...]
    answer_fingerprint: str
    reason: str | None = None
    canonical_result: Any | None = None


class FinancialQueryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FinancialQueryResult:
    operation: str
    amount: Any | None
    groups: tuple[dict[str, Any], ...]
    currency: str | None
    currency_authority: str | None
    observation_count: int
    scope: Any
    evidence_references: tuple[str, ...]
    source_references: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()


class GovernedAskNexoraService:
    """Answer only from PUE-008/PUE-007/ACT-005 or canonical graph evidence."""

    def __init__(
        self,
        *,
        measurement_service=None,
        financial_service=None,
        financial_context=None,
        registry=None,
        graph=None,
        bindings: Iterable[Any] = (),
        activation_resolver=None,
        interpreter=None,
        policy=None,
        operations=None,
        operation_context=None,
        intelligence_service=None,
    ) -> None:
        self.measurement_service = measurement_service
        self.financial_service = financial_service
        self.financial_context = financial_context
        self.registry = registry
        self.graph = graph
        self.bindings = tuple(bindings)
        self.activation_resolver = activation_resolver
        self.interpreter = interpreter or DeterministicAnalyticalInterpreter()
        self.policy = policy or InterpretationPolicy()
        self.operations = operations
        self.operation_context = operation_context
        self.intelligence_service = intelligence_service

    def ask(
        self,
        question: str,
        *,
        scope,
        actor_id: str = "ask-nexora",
        admission=None,
        actor=None,
        bindings: Iterable[Any] | None = None,
    ) -> GovernedAskResponse:
        from universal_evidence.operations import (
            FailureClass,
            GovernedEventType,
            ReasonCode,
            Severity,
            observe,
            workflow_context,
        )

        context = workflow_context(self.operation_context, scope, actor=actor, actor_id=actor_id)
        reference = fingerprint(scope, question)
        refs = {"question": reference}
        observe(
            self.operations,
            GovernedEventType.ASK_RECEIVED,
            context,
            audit=False,
            references=refs,
        )
        response = self._ask(
            question,
            scope=scope,
            actor_id=actor_id,
            admission=admission,
            actor=actor,
            bindings=bindings,
        )
        observe(
            self.operations,
            GovernedEventType.ASK_INTERPRETED,
            context,
            audit=False,
            references=refs,
            attributes={"question_class": response.question_class, "state": response.state.value},
        )
        if response.state is AskState.SUPPORTED:
            for event_type in (
                GovernedEventType.ASK_AUTHORIZED,
                GovernedEventType.ASK_EXECUTED,
                GovernedEventType.ASK_ANSWER_COMPOSED,
            ):
                observe(
                    self.operations,
                    event_type,
                    context,
                    audit=False,
                    references={**refs, "result": response.answer_fingerprint},
                )
        elif response.state is AskState.UNSUPPORTED:
            observe(
                self.operations,
                GovernedEventType.ASK_UNSUPPORTED,
                context,
                audit=False,
                severity=Severity.INFO,
                outcome="BLOCKED",
                failure_class=FailureClass.UNSUPPORTED,
                reason_code=ReasonCode.UNSUPPORTED_QUESTION,
                references=refs,
            )
        else:
            reason = (
                ReasonCode.POTENTIAL_INJECTION
                if self._injection_like(" ".join(str(question or "").split()))
                else ReasonCode.KILL_SWITCH_ACTIVE
                if self._activation_blocked(scope)
                else ReasonCode.EXECUTION_NOT_AUTHORIZED
            )
            observe(
                self.operations,
                GovernedEventType.ASK_BLOCKED,
                context,
                audit=False,
                severity=Severity.INFO,
                outcome="BLOCKED",
                failure_class=FailureClass.EXPECTED_BLOCK,
                reason_code=reason,
                references=refs,
            )
            if reason is ReasonCode.POTENTIAL_INJECTION:
                observe(
                    self.operations,
                    GovernedEventType.POTENTIAL_INJECTION_BLOCKED,
                    context,
                    audit=False,
                    severity=Severity.SECURITY,
                    outcome="BLOCKED",
                    failure_class=FailureClass.SECURITY_REJECTION,
                    reason_code=reason,
                    references=refs,
                    attributes={"category": "governance_bypass", "source_type": "user_question"},
                )
        return response

    def _ask(
        self,
        question: str,
        *,
        scope,
        actor_id: str = "ask-nexora",
        admission=None,
        actor=None,
        bindings: Iterable[Any] | None = None,
    ) -> GovernedAskResponse:
        text = " ".join(str(question or "").split())
        source_bindings = tuple(self.bindings if bindings is None else bindings)
        if self._activation_blocked(scope):
            return self._finish(
                AskState.BLOCKED,
                text,
                "activation",
                "Governed Ask Nexora is suppressed by the active kill switch.",
            )
        if not text:
            return self._finish(AskState.INSUFFICIENT, text, "unknown", "No question was supplied.")
        if self._injection_like(text):
            return self._finish(
                AskState.BLOCKED,
                text,
                "governance",
                "Governance cannot be bypassed by question text or uploaded data.",
            )
        if self.intelligence_service is not None:
            canonical = self._canonical_query(text, scope)
            if canonical is not None:
                return canonical
        if self._unsupported(text):
            return self._finish(
                AskState.UNSUPPORTED,
                text,
                "unsupported",
                "UNSUPPORTED / NOT AUTHORIZED. No governed capability supports this request.",
            )
        if self._is_financial(text):
            return self._financial(text, scope)
        if self._is_measurement(text):
            return self._measurement(text, scope, admission, actor, actor_id)
        if self.registry is None or self.graph is None:
            return self._finish(
                AskState.INSUFFICIENT,
                text,
                self._question_class(text),
                "I do not have enough governed evidence to answer that yet.",
            )
        return self._enterprise(text, scope, source_bindings)

    def _canonical_query(self, text, scope):
        """Map bounded product intents to the shared P5 result, without calculating."""
        lower = text.casefold()
        family = None
        entity_id = None
        dimensions = {
            "business service": "business_service",
            "cost center": "cost_center",
            "cost centre": "cost_center",
            "application": "application",
            "owner": "owner",
            "technology": "technology",
            "domain": "domain",
        }
        if "source health" in lower:
            family = "source_health"
        elif "source" in lower or "provenance" in lower or "evidence" in lower:
            family = "source_explanation"
        elif "conflict" in lower:
            family = "conflicted_context"
        elif "unresolved" in lower or "unknown context" in lower:
            family = "unresolved_context"
        elif "depend" in lower:
            family = "dependencies_for_entity"
        elif "impact" in lower:
            family = "impact_of_change"
        elif "who own" in lower or "ownership" in lower:
            family = "owner_for_entity"
        elif "business service" in lower and "application" in lower and "spend" not in lower:
            family = "business_service_for_application"
        elif ("cost center" in lower or "cost centre" in lower) and "spend" not in lower:
            family = "cost_center_for_entity"
        elif "opportunit" in lower and any(
            word in lower for word in ("entity", "application", "technology")
        ):
            family = "opportunities_for_entity"
        elif "saving" in lower or "optimization" in lower:
            dimension = next(
                (value for label, value in dimensions.items() if f"by {label}" in lower), None
            )
            family = f"savings_by_{dimension}" if dimension else "optimization_summary"
        elif "spend" in lower:
            dimension = next(
                (value for label, value in dimensions.items() if f"by {label}" in lower), None
            )
            family = f"spend_by_{dimension}" if dimension else "enterprise_spend_summary"
        if family is None:
            return None
        if family in {
            "owner_for_entity",
            "business_service_for_application",
            "cost_center_for_entity",
            "dependencies_for_entity",
            "impact_of_change",
            "opportunities_for_entity",
        }:
            entity_id = self._subject(text) or None
        try:
            result = self.intelligence_service.query(scope, family, entity_id=entity_id)
        except PermissionError:
            return self._finish(
                AskState.BLOCKED,
                text,
                "canonical",
                "The requested authority is outside the active scope.",
            )
        state_name = result.availability.value
        supported = state_name in {"AVAILABLE", "PARTIAL", "STALE", "CONFLICTED", "QUARANTINED"}
        ask_state = (
            AskState.STALE
            if state_name == "STALE"
            else AskState.SUPPORTED
            if supported
            else AskState.INSUFFICIENT
        )
        answer = self._canonical_answer(result)
        citations = tuple(
            {"type": "canonical_evidence", "reference": ref} for ref in result.evidence_references
        )
        provenance = (
            {
                "query_family": result.query_family,
                "scope": result.scope,
                "availability": state_name,
                "authority": result.authority,
                "result_fingerprint": result.fingerprint,
                "period": result.period,
                "currency": result.currency,
                "coverage": result.coverage,
                "freshness": result.freshness,
                "conflicts": result.conflicts,
            },
        )
        return self._finish(
            ask_state,
            text,
            "canonical",
            answer,
            citations=citations,
            provenance=provenance,
            canonical_result=result,
        )

    @staticmethod
    def _canonical_answer(result):
        state = result.availability.value
        if state not in {"AVAILABLE", "PARTIAL"}:
            reason = ", ".join(result.reason_codes) or "canonical evidence is unavailable"
            return f"{state}: {reason}."
        suffix = (
            f" {result.currency}" if result.currency else f" {result.unit}" if result.unit else ""
        )
        if result.breakdown:
            groups = "; ".join(
                f"{row.label}: "
                f"{row.value if row.value is not None else row.availability.value}{suffix}"
                for row in result.breakdown
            )
            return (
                f"{result.query_family.replace('_', ' ').title()}: {groups}. Availability: {state}."
            )
        title = result.query_family.replace("_", " ").title()
        return f"{title}: {result.value}{suffix}. Availability: {state}."

    def _financial(self, text, scope):
        if self.financial_service is None or self.financial_context is None:
            return self._finish(
                AskState.INSUFFICIENT,
                text,
                "financial",
                "I do not have enough governed financial evidence to answer that yet.",
            )
        if (
            self.financial_context.organization_id != scope.organization_id
            or self.financial_context.tenant_id != scope.tenant_id
        ):
            return self._finish(
                AskState.BLOCKED,
                text,
                "financial",
                "The requested financial authority is outside the active scope.",
            )
        try:
            result = self._financial_query(text, scope)
        except (FinancialQueryError, ValueError, TypeError) as exc:
            return self._finish(AskState.BLOCKED, text, "financial", str(exc))
        if result.operation in {"TOTAL_SPEND", "SPEND_BY_SERVICE", "SPEND_BY_REGION"} and (
            result.currency is None or result.currency_authority is None
        ):
            return self._finish(
                AskState.BLOCKED,
                text,
                "financial",
                "Governed currency evidence is required before answering this question.",
            )
        if result.operation == "EVIDENCE":
            answer = (
                f"The result is supported by {result.observation_count} canonical financial "
                "observations under governed financial authority."
            )
        elif result.operation == "SOURCE":
            answer = f"The information was supplied by: {', '.join(result.source_references)}."
        elif result.operation == "UNRESOLVED":
            answer = (
                "Known unresolved information: "
                + (", ".join(result.unresolved) if result.unresolved else "none")
                + "."
            )
        elif result.operation == "TOTAL_SPEND":
            answer = f"Governed total spend: {result.amount} {result.currency}."
        else:
            groups = ", ".join(
                f"{item['label']}: {item['amount']} {result.currency}" for item in result.groups
            )
            dimension = result.operation.removeprefix("SPEND_BY_").casefold()
            answer = f"Governed spend by {dimension}: {groups}."
        return self._finish(
            AskState.SUPPORTED,
            text,
            "financial",
            answer,
            citations=tuple(
                {"type": "canonical_financial_observation", "reference": reference}
                for reference in result.evidence_references
            ),
            provenance=(
                {
                    "scope": result.scope,
                    "operation": result.operation,
                    "currency": result.currency,
                    "currency_authority": result.currency_authority,
                    "observation_count": result.observation_count,
                    "evidence_references": result.evidence_references,
                    "source_references": result.source_references,
                    "unresolved": result.unresolved,
                },
            ),
        )

    def _financial_query(self, text, scope):
        service = self.financial_service
        context = self.financial_context
        posture = service.get_financial_posture(context)
        currency = getattr(posture, "currency", None)
        amount = getattr(posture, "cloud_spend", None)
        has_data = getattr(posture, "has_data", False)
        if isinstance(posture, dict):
            currency = posture.get("currency")
            amount = posture.get("total_ingested_spend")
            has_data = bool(posture.get("source_rows"))
        if not has_data:
            raise FinancialQueryError("No governed financial observations are available.")
        evidence_method = getattr(service, "get_financial_evidence", None)
        evidence = tuple(evidence_method(context)) if evidence_method else ()
        if not evidence:
            raise FinancialQueryError("No governed financial evidence metadata is available.")
        operation = "TOTAL_SPEND"
        rows = ()
        lower = text.casefold()
        if "source" in lower:
            operation = "SOURCE"
        elif "unresolved" in lower or "unknown" in lower:
            operation = "UNRESOLVED"
        elif "evidence" in lower or "provenance" in lower or "supports" in lower:
            operation = "EVIDENCE"
        elif "region" in lower:
            operation = "SPEND_BY_REGION"
            rows = service.get_spend_by_region(context)
        elif "service" in lower:
            operation = "SPEND_BY_SERVICE"
            rows = service.get_spend_by_service(context)
        evidence_references = tuple(dict.fromkeys(item["observation_id"] for item in evidence))
        source_references = tuple(
            dict.fromkeys(
                reference
                for item in evidence
                for reference in (
                    f"source:{item.get('source_id')}" if item.get("source_id") else None,
                    f"file:{item.get('file_id')}" if item.get("file_id") else None,
                )
                if reference
            )
        )
        represented_dimensions = {key for item in evidence for key in item.get("dimensions", {})}
        unresolved = tuple(
            label
            for key, label in (
                ("application", "application context"),
                ("business_service", "business service context"),
                ("owner", "owner context"),
                ("team", "team context"),
                ("department", "department context"),
                ("cost_center", "cost center context"),
            )
            if key not in represented_dimensions
        )
        groups = tuple(
            {
                "label": row.get("service", row.get("region", "UNKNOWN")),
                "amount": row.get("amount"),
            }
            for row in sorted(rows, key=lambda item: item.get("amount", 0), reverse=True)
        )
        return FinancialQueryResult(
            operation,
            amount,
            groups,
            currency,
            "CANONICAL_FINANCIAL_AUTHORITY",
            len(evidence),
            (scope.organization_id, scope.tenant_id),
            evidence_references,
            source_references,
            unresolved,
        )

    def _measurement(self, text, scope, admission, actor, actor_id):
        if self.measurement_service is None or admission is None or actor is None:
            return self._finish(
                AskState.BLOCKED,
                text,
                "measurement",
                "A governed evidence admission and execution authority are required.",
            )
        try:
            _runs, assessment = self.measurement_service._current(admission, actor=actor)
        except PermissionError as exc:
            return self._finish(
                AskState.BLOCKED,
                text,
                "measurement",
                str(exc),
            )
        catalog = build_concept_catalog(
            self.measurement_service.normalization_service.capabilities.repository,
            scope,
            self.policy,
        )
        if assessment is None or catalog is None:
            return self._finish(
                AskState.BLOCKED,
                text,
                "measurement",
                "No current governed capability assessment is available.",
            )
        interpreted = self.interpreter.interpret(
            NaturalLanguageQuestion(
                "act008-question-" + fingerprint(scope, text)[:24],
                text,
                scope,
                actor_id,
                "HUMAN",
                self.policy.question_version,
                admission.created_at,
            ),
            catalog,
        )
        if interpreted.status is not InterpretationStatus.INTERPRETED:
            state = {
                InterpretationStatus.AMBIGUOUS: AskState.AMBIGUOUS,
                InterpretationStatus.UNSUPPORTED: AskState.UNSUPPORTED,
            }.get(interpreted.status, AskState.BLOCKED)
            return self._finish(
                state,
                text,
                "measurement",
                "; ".join(interpreted.explanation)
                or "The governed interpretation cannot authorize this question.",
                interpretation=interpreted,
            )
        intent = interpreted.primary_intent
        planning, result = self.measurement_service.execute(
            admission,
            actor=actor,
            intent_type=intent.intent_type,
            measure_concept_id=intent.measure_concept_id,
            dimension_concept_ids=intent.dimension_concept_ids,
        )
        if planning.plan.planning_status.value != "READY" or result is None:
            return self._finish(
                AskState.BLOCKED,
                text,
                "measurement",
                "; ".join(reason.value for reason in planning.plan.reason_codes)
                or "The requested measurement is not currently authorized.",
                interpretation=interpreted,
                plan=planning,
            )
        answer = self._format_measurement(intent.intent_type, result)
        return self._finish(
            AskState.SUPPORTED,
            text,
            "measurement",
            answer,
            interpretation=interpreted,
            plan=planning,
            execution=result,
            provenance=(
                {
                    "scope": scope.key,
                    "plan_id": planning.plan.plan_id,
                    "result_fingerprint": result.result_fingerprint,
                },
            ),
        )

    def _enterprise(self, text, scope, bindings):
        matches = self._entity_matches(self._subject(text), scope)
        if not matches and "applications" in text.casefold():
            matches = tuple(
                item
                for item in self.registry.list_entities()
                if item.entity_type.value == "application"
            )
        if len(matches) > 1:
            return self._finish(
                AskState.AMBIGUOUS,
                text,
                self._question_class(text),
                "More than one governed canonical entity matches; specify the entity type.",
            )
        if not matches:
            return self._finish(
                AskState.INSUFFICIENT,
                text,
                self._question_class(text),
                "I do not have enough governed evidence to answer that yet.",
            )
        entity = matches[0]
        citations = (
            {
                "type": "canonical_entity",
                "canonical_id": entity.canonical_id,
                "entity_type": entity.entity_type.value,
            },
        )
        provenance = (
            {
                "canonical_id": entity.canonical_id,
                "source_system": entity.source_system,
                "source_identifier": entity.source_identifier,
            },
        )
        lower = text.casefold()
        if "source" in lower and "describe" in lower:
            related = tuple(
                item for item in bindings if item.canonical_entity_id == entity.canonical_id
            )
            if not related:
                return self._finish(
                    AskState.INSUFFICIENT,
                    text,
                    "provenance",
                    "No governed cross-source bindings are available for this entity.",
                    citations=citations,
                    provenance=provenance,
                )
            sources = sorted({f"{item.source_system}:{item.source_identifier}" for item in related})
            return self._finish(
                AskState.SUPPORTED,
                text,
                "provenance",
                f"{entity.display_name} is described by governed sources: {', '.join(sources)}.",
                citations=citations,
                provenance=(*provenance, {"bindings": sources}),
            )
        if "own" in lower or "owner" in lower:
            owners = self.graph.get_owners(entity.canonical_id)
            if not owners:
                return self._finish(
                    AskState.INSUFFICIENT,
                    text,
                    "relationship",
                    "I do not have enough governed evidence to answer that yet.",
                    citations=citations,
                    provenance=provenance,
                )
            return self._finish(
                AskState.SUPPORTED,
                text,
                "relationship",
                f"{entity.display_name} is owned by "
                f"{', '.join(item.display_name for item in owners)}.",
                citations=citations,
                provenance=(*provenance, {"relationship": "owned_by"}),
            )
        if "cost centre" in lower or "cost center" in lower:
            relationships = self.graph.get_relationships(
                entity.canonical_id, relationship_type="funded_by"
            )
            targets = [
                self.registry.get_entity(
                    item.target_entity_id
                    if item.source_entity_id == entity.id
                    else item.source_entity_id
                )
                for item in relationships
            ]
            if not targets:
                return self._finish(
                    AskState.INSUFFICIENT,
                    text,
                    "relationship",
                    "I do not have enough governed evidence to answer that yet.",
                    citations=citations,
                    provenance=provenance,
                )
            return self._finish(
                AskState.SUPPORTED,
                text,
                "relationship",
                f"{entity.display_name} is assigned to "
                f"{', '.join(item.display_name for item in targets)}.",
                citations=citations,
                provenance=(*provenance, {"relationship": "funded_by"}),
            )
        if "depend" in lower or "uses" in lower:
            paths = self.graph.get_dependencies(entity.canonical_id)
            if not paths:
                return self._finish(
                    AskState.INSUFFICIENT,
                    text,
                    "relationship",
                    "I do not have enough governed evidence to answer that yet.",
                    citations=citations,
                    provenance=provenance,
                )
            names = sorted({path.entities[-1].display_name for path in paths})
            return self._finish(
                AskState.SUPPORTED,
                text,
                "relationship",
                f"{entity.display_name} depends on {', '.join(names)}.",
                citations=citations,
                provenance=(*provenance, {"relationship": "dependency_path"}),
            )
        if entity.entity_type.value == "application" and "application" in lower:
            return self._finish(
                AskState.SUPPORTED,
                text,
                "entity",
                f"Known application: {entity.display_name}.",
                citations=citations,
                provenance=provenance,
            )
        return self._finish(
            AskState.SUPPORTED,
            text,
            "entity",
            f"Canonical entity: {entity.display_name} ({entity.entity_type.value}).",
            citations=citations,
            provenance=provenance,
        )

    def _entity_matches(self, subject, scope):
        if not subject:
            return ()
        return tuple(
            item
            for item in self.registry.list_entities()
            if item.organization_id == scope.organization_id
            and item.tenant_id == scope.tenant_id
            and self._norm(item.display_name) == self._norm(subject)
        )

    @staticmethod
    def _subject(text):
        ignored = {
            "who",
            "what",
            "which",
            "where",
            "why",
            "tell",
            "show",
            "how",
            "owns",
            "owner",
            "assigned",
            "to",
            "me",
            "about",
            "cost",
            "centre",
            "center",
            "is",
            "sources",
            "source",
            "describe",
            "does",
            "depend",
            "on",
        }
        candidates = re.findall(r"\b(?:[A-Za-z][A-Za-z0-9_-]*|i-[a-z0-9-]+)\b", text)
        return next(
            (candidate for candidate in candidates if candidate.casefold() not in ignored),
            "",
        )

    @staticmethod
    def _is_financial(text):
        lower = text.casefold()
        return (
            "spend" in lower
            and any(term in lower for term in ("total", "service", "region", "breakdown", "top"))
        ) or any(
            term in lower
            for term in (
                "what evidence supports",
                "which source supplied",
                "what information is unresolved",
            )
        )

    @staticmethod
    def _is_measurement(text):
        lower = text.casefold()
        return any(
            term in lower
            for term in (
                "how many records",
                "how many detail records",
                "total cost",
                "total governed cost",
                "cost by service",
                "cost by",
            )
        )

    @staticmethod
    def _question_class(text):
        lower = text.casefold()
        if "source" in lower or "provenance" in lower:
            return "provenance"
        if any(term in lower for term in ("depend", "uses", "owner", "cost centre", "cost center")):
            return "relationship"
        return "entity"

    @staticmethod
    def _injection_like(text):
        lower = text.casefold()
        return any(
            term in lower
            for term in (
                "ignore governance",
                "ignore previous instructions",
                "use raw",
                "calculate directly",
                "expose all tenant",
            )
        )

    @staticmethod
    def _unsupported(text):
        lower = text.casefold()
        return any(
            term in lower
            for term in ("forecast", "optimize", "optimization", "convert", "fx", "terminate")
        )

    def _activation_blocked(self, scope):
        if self.activation_resolver is None:
            return False
        from universal_evidence.activation import ActivationScope, RoutingReason, ScopeLevel

        analysis_id = getattr(scope, "analysis_id", None)
        prospect_id = getattr(scope, "prospect_id", None)
        tenant_id = getattr(scope, "tenant_id", None)
        organization_id = getattr(scope, "organization_id", None)
        level = (
            ScopeLevel.ANALYSIS
            if analysis_id
            else ScopeLevel.PROSPECT
            if prospect_id
            else ScopeLevel.TENANT
            if tenant_id
            else ScopeLevel.ORGANIZATION
            if organization_id
            else ScopeLevel.GLOBAL
        )
        activation = self.activation_resolver.resolve(
            ActivationScope(
                level,
                organization_id=organization_id,
                tenant_id=tenant_id,
                prospect_id=prospect_id,
                analysis_id=analysis_id,
            )
        )
        return RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes

    @staticmethod
    def _format_measurement(intent_type, result):
        if intent_type is AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION:
            groups = "; ".join(
                f"{group.dimension_values[0][1]} = {group.value} "
                f"{result.currency_or_unit or ''}".strip()
                for group in result.groups
            )
            return f"Governed cost by service: {groups}."
        unit = f" {result.currency_or_unit}" if result.currency_or_unit else ""
        return f"Governed result: {result.scalar_value}{unit}."

    def _finish(
        self,
        state,
        question,
        question_class,
        answer,
        *,
        interpretation=None,
        plan=None,
        execution=None,
        citations=(),
        provenance=(),
        reason=None,
        canonical_result=None,
    ):
        identity = fingerprint(
            state.value,
            question,
            question_class,
            self._stable_identity(interpretation),
            self._stable_identity(plan),
            self._stable_identity(execution),
            citations,
            provenance,
            reason,
            getattr(canonical_result, "fingerprint", None),
        )
        return GovernedAskResponse(
            state,
            answer,
            question,
            question_class,
            interpretation,
            plan,
            execution,
            tuple(citations),
            tuple(provenance),
            identity,
            reason,
            canonical_result,
        )

    @staticmethod
    def _stable_identity(value):
        if value is None:
            return None
        for attribute in ("fingerprint", "plan_fingerprint", "result_fingerprint"):
            identity = getattr(value, attribute, None)
            if identity:
                return identity
        nested = getattr(value, "plan", None)
        if nested is not None:
            identity = getattr(nested, "plan_fingerprint", None)
            if identity:
                return identity
        return str(value)

    @staticmethod
    def _norm(value):
        return " ".join(str(value or "").casefold().split())
