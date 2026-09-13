from __future__ import annotations

import pytest

from data_fabric.foundation import TenantContext
from enterprise_copilot.semantic_planner import (
    CapabilityDescriptor,
    SemanticPlanError,
    execute_semantic_plan,
    plan_question,
    validate_semantic_plan,
)
from tests.universal_evidence.test_governed_aggregation_execution import single_currency

SCOPE = TenantContext("org-1", "tenant-1")
CATALOGUE = (
    CapabilityDescriptor(
        "cap_cost",
        "MONETARY_TOTAL",
        "financial",
        ("cost_total",),
        ("service", "license_type"),
        ("SUM",),
        ("service", "license_type"),
        True,
        False,
        "auditor",
        "missing attribution remains UNKNOWN",
        "source rows and authorization are retained",
        ("measure", "filter"),
    ),
    CapabilityDescriptor(
        "cap_apps",
        "APPLICATION_INVENTORY",
        "inventory",
        (),
        ("application",),
        ("COUNT",),
        ("application",),
        True,
        False,
        "auditor",
        "missing application evidence remains UNKNOWN",
        "canonical application provenance is retained",
        (),
    ),
)


def plan(**overrides):
    value = {
        "interpretation": "SaaS license savings by application",
        "entities": ["application"],
        "measures": ["cost_total"],
        "dimensions": ["license_type"],
        "filters": [{"dimension": "license_type", "operator": "EQUALS", "value": "SaaS"}],
        "time_range": None,
        "grouping": ["license_type"],
        "ordering": None,
        "steps": [
            {
                "step_id": "step_cost",
                "capability_id": "cap_cost",
                "operation": "SUM",
                "parameters": {"measure": "cost_total", "filter": "SaaS"},
                "depends_on": [],
            }
        ],
        "synthesis": "Answer with governed cost and disclose missing mappings.",
    }
    value.update(overrides)
    return value


def test_unseen_domain_constraint_survives_validation_and_execution():
    validated = validate_semantic_plan(plan(), catalogue=CATALOGUE, scope=SCOPE, role="auditor")
    calls = []
    results = execute_semantic_plan(
        validated,
        handlers={
            "cap_cost": lambda **kwargs: calls.append(kwargs) or {"cost": 100, "domain": "SaaS"}
        },
    )
    assert validated.filters[0]["value"] == "SaaS"
    assert calls[0]["scope"] == SCOPE
    assert results[0]["domain"] == "SaaS"


@pytest.mark.parametrize(
    "change",
    [
        {
            "steps": [
                {
                    "step_id": "step_bad",
                    "capability_id": "unknown",
                    "operation": "SUM",
                    "parameters": {},
                    "depends_on": [],
                }
            ]
        },
        {
            "steps": [
                {
                    "step_id": "step_bad",
                    "capability_id": "cap_cost",
                    "operation": "DELETE",
                    "parameters": {},
                    "depends_on": [],
                }
            ]
        },
        {
            "steps": [
                {
                    "step_id": "step_bad",
                    "capability_id": "cap_cost",
                    "operation": "SUM",
                    "parameters": {"sql": "SELECT 1"},
                    "depends_on": [],
                }
            ]
        },
    ],
)
def test_invalid_or_unrestricted_plans_fail_closed(change):
    with pytest.raises(SemanticPlanError):
        validate_semantic_plan(plan(**change), catalogue=CATALOGUE, scope=SCOPE, role="auditor")


def test_multistep_dependencies_must_be_ordered_and_registered():
    value = plan(
        dimensions=[],
        measures=[],
        filters=[],
        grouping=[],
        steps=[
            {
                "step_id": "step_apps",
                "capability_id": "cap_apps",
                "operation": "COUNT",
                "parameters": {},
                "depends_on": [],
            },
            {
                "step_id": "step_cost",
                "capability_id": "cap_cost",
                "operation": "SUM",
                "parameters": {},
                "depends_on": ["step_apps"],
            },
        ]
    )
    validated = validate_semantic_plan(value, catalogue=CATALOGUE, scope=SCOPE, role="auditor")
    observed = []
    execute_semantic_plan(
        validated,
        handlers={
            "cap_apps": lambda **kwargs: observed.append("apps") or {"apps": 2},
            "cap_cost": lambda **kwargs: observed.append(
                kwargs["dependencies"][0]["apps"]
            )
            or {"cost": 100},
        },
    )
    assert observed == ["apps", 2]


def test_unknown_dimension_fails_closed():
    with pytest.raises(SemanticPlanError, match="unknown dimension"):
        validate_semantic_plan(
            plan(dimensions=["tower"]), catalogue=CATALOGUE, scope=SCOPE, role="auditor"
        )


def test_plan_question_binds_current_assessment_and_conversation():
    _, _, assessment = single_currency()
    observed = {}

    class Provider:
        def plan(self, **kwargs):
            observed.update(kwargs)
            descriptor = kwargs["catalogue"][0]
            return {
                "interpretation": "total governed cost",
                "entities": [],
                "measures": [],
                "dimensions": [],
                "filters": [],
                "grouping": [],
                "steps": [
                    {
                        "step_id": "step_cost",
                        "capability_id": descriptor.capability_id,
                        "operation": descriptor.operations[0],
                        "parameters": {},
                        "depends_on": [],
                    }
                ],
                "synthesis": "Answer only from governed evidence.",
            }

    result = plan_question(
        Provider(),
        question="What is the total cost, actually?",
        assessment=assessment,
        role="auditor",
        conversation=(("user", "Which account did I mean?"),),
    )
    assert result.scope == assessment.scope
    assert observed["question"].endswith("actually?")
    assert observed["conversation"] == (("user", "Which account did I mean?"),)
