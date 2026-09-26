from __future__ import annotations

import os
import subprocess
import sys

from data_fabric.foundation import TenantContext
from enterprise_registry.relationship_intelligence import (
    RelationshipIntelligenceService,
)
from services.demo_enterprise_topology import (
    demo_enterprise_topology,
)
from services.demo_tenant_service import DEMO_ORGANIZATION_ID
from services.enterprise_registry_composition import (
    enterprise_registry_service,
)
from services.relationship_intelligence_composition import (
    relationship_intelligence_service,
)


def _context(tenant_id: str = "demo-topology-test"):
    return TenantContext(
        DEMO_ORGANIZATION_ID,
        tenant_id,
    )


def test_demo_topology_projects_certified_twin_path(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    context = _context()
    entities, relationships = demo_enterprise_topology(context)

    names = {
        entity.display_name: entity
        for entity in entities
    }

    assert "Global Digital Checkout" in names
    assert "Checkout Orchestration Platform" in names
    assert "End-of-support runtime" in names
    assert "Hyperscale Cloud A" in names

    checkout = names["Global Digital Checkout"]

    assert checkout.entity_type.value == "business_service"
    assert checkout.source_system == "golden_demo"
    assert checkout.provenance_reference
    assert checkout.organization_id == context.organization_id
    assert checkout.tenant_id == context.tenant_id

    assert relationships

    assert all(
        relationship.organization_id
        == context.organization_id
        for relationship in relationships
    )

    assert all(
        relationship.tenant_id == context.tenant_id
        for relationship in relationships
    )

    assert all(
        relationship.evidence
        and relationship.provenance_reference
        for relationship in relationships
    )


def test_checkout_traverses_existing_relationship_intelligence(
    monkeypatch,
):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    context = _context()
    entities, relationships = demo_enterprise_topology(context)

    service = RelationshipIntelligenceService(
        context,
        role="executive",
        entities=entities,
        relationships=relationships,
    )

    checkout = next(
        entity
        for entity in entities
        if entity.display_name == "Global Digital Checkout"
    )

    paths = service.get_dependencies(
        checkout.canonical_id,
        max_hops=3,
    )

    reached = {
        entity.display_name
        for path in paths
        for entity in path.entities
    }

    assert {
        "Checkout Orchestration Platform",
        "End-of-support runtime",
        "Hyperscale Cloud A",
    }.issubset(reached)

    assert all(
        relationship.evidence
        for path in paths
        for relationship in path.relationships
    )


def test_demo_topology_flows_through_canonical_compositions(
    monkeypatch,
):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    context = _context("composition-test")

    registry = enterprise_registry_service(
        context,
        role="executive",
    )

    checkout = next(
        entity
        for entity in registry.list_entities()
        if entity.display_name == "Global Digital Checkout"
    )

    assert checkout.entity_type.value == "business_service"
    assert checkout.source_system == "golden_demo"

    relationship_service = relationship_intelligence_service(
        context,
        role="executive",
    )

    paths = relationship_service.get_dependencies(
        checkout.canonical_id,
        max_hops=3,
    )

    reached = {
        entity.display_name
        for path in paths
        for entity in path.entities
    }

    assert {
        "Checkout Orchestration Platform",
        "End-of-support runtime",
        "Hyperscale Cloud A",
    }.issubset(reached)


def test_demo_projection_is_disabled_outside_demo_mode(
    monkeypatch,
):
    monkeypatch.delenv(
        "NEXORA_DEMO_MODE",
        raising=False,
    )

    context = _context("isolation-test")

    entities, relationships = demo_enterprise_topology(
        context
    )

    assert entities == ()
    assert relationships == ()

    registry = enterprise_registry_service(
        context,
        role="executive",
    )

    assert not any(
        entity.source_system == "golden_demo"
        for entity in registry.list_entities()
    )


def test_demo_projection_does_not_invent_business_unit(
    monkeypatch,
):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    entities, _ = demo_enterprise_topology(_context())

    assert not any(
        entity.entity_type.value == "business_unit"
        for entity in entities
    )


def test_demo_projection_does_not_embed_financial_amounts(
    monkeypatch,
):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    entities, relationships = demo_enterprise_topology(
        _context()
    )

    payload = repr((entities, relationships))

    assert "87000000" not in payload
    assert "214000000" not in payload
    assert "87,000,000" not in payload
    assert "214,000,000" not in payload


def test_copilot_import_order_is_stable():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.getcwd()

    commands = (
        (
            "from services.governed_enterprise_capabilities "
            "import GovernedEnterpriseCapabilities; "
            "from enterprise_copilot.semantic_planner "
            "import CapabilityDescriptor"
        ),
        (
            "import enterprise_copilot; "
            "import enterprise_copilot.composition; "
            "from services.governed_enterprise_capabilities "
            "import GovernedEnterpriseCapabilities"
        ),
    )

    for command in commands:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                command,
            ],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0, result.stderr
