"""Provider-neutral semantic planning over governed capability metadata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from universal_evidence.capability import CapabilityAssessment, CapabilityScope


class SemanticPlanError(ValueError):
    """Raised when a model plan cannot be proven safe and governed."""


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability_id: str
    capability_name: str
    domain: str
    measures: tuple[str, ...]
    dimensions: tuple[str, ...]
    operations: tuple[str, ...]
    filters: tuple[str, ...]
    grouping: bool
    temporal: bool
    authorization_scope: str
    unknown_behavior: str
    provenance_behavior: str
    parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticPlanStep:
    step_id: str
    capability_id: str
    operation: str
    parameters: Mapping[str, Any]
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticPlan:
    interpretation: str
    entities: tuple[str, ...]
    measures: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[Mapping[str, Any], ...]
    time_range: Mapping[str, Any] | None
    grouping: tuple[str, ...]
    ordering: Mapping[str, Any] | None
    steps: tuple[SemanticPlanStep, ...]
    synthesis: str
    scope: CapabilityScope


class SemanticPlannerProvider(Protocol):
    def plan(
        self,
        *,
        question: str,
        catalogue: tuple[CapabilityDescriptor, ...],
        scope: CapabilityScope,
        conversation: tuple[Mapping[str, str], ...] = (),
    ) -> Mapping[str, Any]: ...


def plan_question(
    provider: SemanticPlannerProvider,
    *,
    question: str,
    assessment: CapabilityAssessment,
    role: str,
    conversation: tuple[Mapping[str, str], ...] = (),
) -> SemanticPlan:
    """Ask an inference provider to plan, then validate against current authority."""

    catalogue = build_capability_catalogue(assessment, role=role)
    payload = provider.plan(
        question=question,
        catalogue=catalogue,
        scope=assessment.scope,
        conversation=conversation,
    )
    return validate_semantic_plan(
        payload,
        catalogue=catalogue,
        scope=assessment.scope,
        role=role,
    )


def build_capability_catalogue(
    assessment: CapabilityAssessment, *, role: str
) -> tuple[CapabilityDescriptor, ...]:
    """Expose current supported authorities without exposing records or repositories."""

    measures_by_capability = {
        item.capability_id: tuple(
            measure.measure_id
            for measure in assessment.measures
            if measure.measure_id in item.supporting_measure_ids
        )
        for item in assessment.capabilities
    }
    dimensions_by_capability = {
        item.capability_id: tuple(
            dimension.dimension_id
            for dimension in assessment.dimensions
            if dimension.dimension_id in item.supporting_dimension_ids
        )
        for item in assessment.capabilities
    }
    descriptors = []
    for capability in assessment.capabilities:
        if capability.state.value != "SUPPORTED":
            continue
        authorizations = tuple(
            item
            for item in assessment.execution_authorizations
            if item.capability_id == capability.capability_id
        )
        operations = tuple(
            sorted(
                {
                    operation.value
                    for item in authorizations
                    for operation in item.authorized_operations
                }
            )
        )
        filters = tuple(
            sorted(
                dimension.dimension_id
                for dimension in assessment.dimensions
                if dimension.dimension_id in dimensions_by_capability[capability.capability_id]
                and dimension.filterable
            )
        )
        descriptors.append(
            CapabilityDescriptor(
                capability.capability_id,
                capability.capability_name,
                capability.capability_name.lower(),
                measures_by_capability[capability.capability_id],
                dimensions_by_capability[capability.capability_id],
                operations,
                filters,
                any(item.dimension_ids for item in authorizations),
                any(item.time_dimension_id for item in authorizations),
                role,
                "unsupported or absent evidence remains UNKNOWN",
                "execution result carries source and authorization provenance",
            )
        )
    return tuple(sorted(descriptors, key=lambda item: item.capability_id))


def validate_semantic_plan(
    payload: Mapping[str, Any],
    *,
    catalogue: tuple[CapabilityDescriptor, ...],
    scope: CapabilityScope,
    role: str,
) -> SemanticPlan:
    """Validate model output as data; never interpret it as executable code."""

    if not isinstance(payload, Mapping):
        raise SemanticPlanError("planner output must be an object")
    serialized = json.dumps(payload, default=str).lower()
    forbidden = (
        "select ",
        "drop ",
        "insert ",
        "update ",
        "delete ",
        "__import__",
        "exec(",
        "shell",
    )
    if any(token in serialized for token in forbidden):
        raise SemanticPlanError("planner output contains an unrestricted operation")
    catalogue_by_id = {item.capability_id: item for item in catalogue}
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps or len(raw_steps) > 8:
        raise SemanticPlanError("plan must contain one to eight ordered steps")
    step_ids = set()
    steps = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, Mapping):
            raise SemanticPlanError("each plan step must be an object")
        step_id = raw_step.get("step_id")
        capability_id = raw_step.get("capability_id")
        operation = raw_step.get("operation")
        parameters = raw_step.get("parameters", {})
        depends_on = raw_step.get("depends_on", [])
        if not isinstance(step_id, str) or not re.fullmatch(r"(?:step_)?[a-z0-9_]{1,40}", step_id):
            raise SemanticPlanError("invalid step identifier")
        if step_id in step_ids:
            raise SemanticPlanError("duplicate step identifier")
        if not isinstance(capability_id, str) or not isinstance(operation, str):
            raise SemanticPlanError("invalid capability or operation")
        descriptor = catalogue_by_id.get(capability_id)
        if descriptor is None:
            raise SemanticPlanError("unknown capability")
        if descriptor.authorization_scope != role:
            raise SemanticPlanError("capability is outside the caller role scope")
        if operation not in descriptor.operations:
            raise SemanticPlanError("operation is not authorized for capability")
        if not isinstance(parameters, Mapping) or not isinstance(depends_on, list):
            raise SemanticPlanError("invalid step parameters or dependencies")
        if any(item not in step_ids for item in depends_on):
            raise SemanticPlanError("step dependency must reference an earlier step")
        parameters = _validate_parameters(parameters, descriptor)
        step_ids.add(step_id)
        steps.append(
            SemanticPlanStep(
                step_id, capability_id, operation, dict(parameters), tuple(depends_on)
            )
        )

    dimensions = _string_tuple(payload.get("dimensions", ()), "dimensions")
    measures = _string_tuple(payload.get("measures", ()), "measures")
    grouping = _string_tuple(payload.get("grouping", ()), "grouping")
    filters = _mapping_tuple(payload.get("filters", ()), "filters")
    # Global constraints apply to every selected step. Never borrow authority
    # from an unselected catalogue entry or silently drop a constraint.
    for step in steps:
        descriptor = catalogue_by_id[step.capability_id]
        if any(item not in descriptor.dimensions for item in dimensions):
            raise SemanticPlanError("unknown dimension for selected capability")
        if any(item not in descriptor.measures for item in measures):
            raise SemanticPlanError("unsupported measure for selected capability")
        if grouping and (
            not descriptor.grouping or any(item not in descriptor.dimensions for item in grouping)
        ):
            raise SemanticPlanError("unsupported grouping for selected capability")
        seen_filters = set()
        for item in filters:
            dimension = item.get("dimension")
            if (
                not isinstance(dimension, str)
                or dimension not in descriptor.filters
                or dimension in seen_filters
                or set(item) != {"dimension", "operator", "value"}
                or item.get("operator") != "EQUALS"
                or not isinstance(item.get("value"), (str, int, float, bool))
            ):
                raise SemanticPlanError("unsupported filter for selected capability")
            seen_filters.add(dimension)
    # No current runtime adapter implements temporal or custom ordering execution.
    if payload.get("time_range") is not None or payload.get("ordering") is not None:
        raise SemanticPlanError("temporal or ordering execution is unsupported")
    if (
        not isinstance(payload.get("interpretation"), str)
        or not payload["interpretation"].strip()
    ):
        raise SemanticPlanError("interpretation is required")
    synthesis = payload.get("synthesis")
    if not isinstance(synthesis, str) or not synthesis.strip():
        raise SemanticPlanError("synthesis request is required")
    return SemanticPlan(
        payload["interpretation"],
        _string_tuple(payload.get("entities", ()), "entities"),
        measures,
        dimensions,
        filters,
        payload.get("time_range") if isinstance(payload.get("time_range"), Mapping) else None,
        grouping,
        payload.get("ordering") if isinstance(payload.get("ordering"), Mapping) else None,
        tuple(steps),
        synthesis,
        scope,
    )


def _validate_parameters(parameters, descriptor):
    # The provider's fixed JSON schema uses null for unused slots.
    nullable_slots = {"query", "result_limit", "filter", "value"}
    normalized = {}
    for key, value in parameters.items():
        if key not in descriptor.parameters:
            if key in nullable_slots and value is None:
                continue
            raise SemanticPlanError("unsupported capability parameter")
        if value is None:
            continue
        if key == "query" and (not isinstance(value, str) or not value.strip()):
            raise SemanticPlanError("query must be nonempty text")
        if key == "result_limit" and (type(value) is not int or not 1 <= value <= 25):
            raise SemanticPlanError("result_limit must be an integer from 1 to 25")
        normalized[key] = value
    return normalized


def _string_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise SemanticPlanError(f"{name} must be a list of strings")
    return tuple(value)


def _mapping_tuple(value: Any, name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, Mapping) for item in value
    ):
        raise SemanticPlanError(f"{name} must be a list of objects")
    return tuple(dict(item) for item in value)


def execute_semantic_plan(
    plan: SemanticPlan,
    *,
    handlers: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Execute only registered capability handlers in validated dependency order."""

    # Resolve all handlers before executing any step.
    if any(not callable(handlers.get(step.capability_id)) for step in plan.steps):
        raise SemanticPlanError("capability handler is not registered")
    results = []
    for step in plan.steps:
        handler = handlers.get(step.capability_id)
        if handler is None or not callable(handler):
            raise SemanticPlanError("capability handler is not registered")
        results.append(
            handler(
                operation=step.operation,
                parameters=dict(step.parameters),
                dependencies=tuple(
                    results[index]
                    for index, previous in enumerate(plan.steps[: len(results)])
                    if previous.step_id in step.depends_on
                ),
                scope=plan.scope,
                constraints={
                    "measures": plan.measures,
                    "dimensions": plan.dimensions,
                    "filters": tuple(dict(item) for item in plan.filters),
                    "grouping": plan.grouping,
                },
            )
        )
    return tuple(results)
