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


class GovernedAskNexoraService:
    """Answer only from PUE-008/PUE-007/ACT-005 or canonical graph evidence."""

    def __init__(
        self,
        *,
        measurement_service=None,
        registry=None,
        graph=None,
        bindings: Iterable[Any] = (),
        activation_resolver=None,
        interpreter=None,
        policy=None,
    ) -> None:
        self.measurement_service = measurement_service
        self.registry = registry
        self.graph = graph
        self.bindings = tuple(bindings)
        self.activation_resolver = activation_resolver
        self.interpreter = interpreter or DeterministicAnalyticalInterpreter()
        self.policy = policy or InterpretationPolicy()

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
        if self._unsupported(text):
            return self._finish(
                AskState.UNSUPPORTED,
                text,
                "unsupported",
                "UNSUPPORTED / NOT AUTHORIZED. No governed capability supports this request.",
            )
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
    def _is_measurement(text):
        lower = text.casefold()
        return any(
            term in lower
            for term in (
                "how many records",
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
