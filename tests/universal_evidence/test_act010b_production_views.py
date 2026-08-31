from __future__ import annotations

from data_fabric.contracts import EntityType
from data_fabric.foundation import TenantContext
from tests.universal_evidence.test_pue_governed_materialization import (
    Activation as MaterializationActivation,
)
from tests.universal_evidence.test_pue_governed_materialization import (
    _fixture as materialization_fixture,
)
from tests.universal_evidence.test_pue_governed_materialization import (
    _service as materialization_service,
)
from tests.universal_evidence.test_pue_governed_reconciliation import (
    ORG,
    TENANT,
    _authorization,
    _entity,
    _observation,
    _service,
)
from tests.universal_evidence.test_pue_governed_reconciliation import (
    Activation as ReconciliationActivation,
)
from universal_evidence.persistence import LifecycleScope, SQLiteLifecycleRepository
from universal_evidence.pilot.materialization import GovernedEntityMaterializationService
from universal_evidence.pilot.production_views import (
    build_enterprise_context,
    build_reconciliation_view,
    confirm_reconciliation,
    load_production_views,
    persist_production_views,
    reject_reconciliation,
)
from universal_evidence.pilot.reconciliation import GovernedIdentityReconciliationService
from universal_evidence.production_workflow import (
    load_configured_production_views,
    load_live_canonical_views,
)


def _controlled_context():
    context = TenantContext("org-act006", "tenant-act006")
    registry, relationships = materialization_service(context)
    report = GovernedEntityMaterializationService(registry, relationships).materialize(
        materialization_fixture(),
        context=context,
        activation=MaterializationActivation(),
    )
    view = build_enterprise_context(
        registry.list_entities(),
        relationships.search_relationships(organization_id=context.organization_id),
        prospect_id="prospect-1",
        analysis_id="analysis-1",
    )
    return context, registry, relationships, report, view


def _matched_reconciliation():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    resource = _entity(
        registry,
        context,
        EntityType.CLOUD_RESOURCE,
        "i-test123",
        "aws",
        "i-test123",
        prospect_id="prospect-1",
    )
    rows = (
        _observation(
            "aws",
            "i-test123",
            EntityType.CLOUD_RESOURCE,
            attributes={"resource_id": "i-test123", "name": "i-test123"},
        ),
        _observation(
            "cmdb",
            "CI-10001",
            EntityType.CLOUD_RESOURCE,
            attributes={"resource_id": "i-test123", "name": "i-test123"},
        ),
    )
    report = GovernedIdentityReconciliationService(registry).reconcile(
        rows, context=context, activation=ReconciliationActivation()
    )
    view = build_reconciliation_view(
        proposals=report.proposals,
        bindings=report.bindings,
        entities=registry.list_entities(),
        observations=rows,
    )
    return registry, resource, report, view


def test_enterprise_context_surfaces_all_controlled_canonical_types_and_counts():
    _context, _registry, _relationships, _report, view = _controlled_context()
    types = {item.entity_type_label: item.name for item in view.entities}
    assert types["Application"] == "Checkout"
    assert types["Business Service"] == "Order Processing"
    assert types["Cloud Resource"] == "i-test123"
    assert types["Owner"] == "Alice"
    assert types["Cost Center"] == "CC-1001"
    assert dict(view.counts)["Applications"] == 1


def test_relationships_use_canonical_targets_and_certified_vocabulary():
    _context, registry, _relationships, _report, view = _controlled_context()
    checkout = next(item for item in view.entities if item.name == "Checkout")
    targets = {(item.relationship, item.target_name) for item in checkout.relationships}
    assert ("owned by", "Alice") in targets
    assert ("assigned to", "CC-1001") in targets
    assert ("supports", "Order Processing") in targets
    assert {item.target_canonical_id for item in checkout.relationships} <= {
        entity.canonical_id for entity in registry.list_entities()
    }


def test_empty_context_and_single_source_reconciliation_are_safe_states():
    context = build_enterprise_context(())
    reconciliation = build_reconciliation_view()
    assert not context.entities
    assert context.empty_message.startswith("No governed enterprise entities")
    assert not reconciliation.items
    assert "multiple governed evidence sources" in reconciliation.empty_message


def test_matched_resource_is_one_card_with_aws_and_cmdb_provenance():
    registry, resource, report, view = _matched_reconciliation()
    assert len(registry.list_entities()) == 1
    assert len(view.items) == 1
    item = view.items[0]
    assert item.canonical_id == resource.canonical_id
    assert item.status == "Matched"
    assert item.sources == ("AWS", "CMDB")
    assert "identifier" in item.match_basis
    assert len({binding.canonical_entity_id for binding in report.bindings}) == 1


def test_possible_same_type_match_needs_review_and_does_not_bind():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    _entity(registry, context, EntityType.APPLICATION, "Payments", "catalogue", "APP-PAY")
    rows = (
        _observation("source-a", "row-a", name="Payments"),
        _observation("source-b", "row-b", name="Payments"),
    )
    report = GovernedIdentityReconciliationService(registry).reconcile(
        rows, context=context, activation=ReconciliationActivation()
    )
    view = build_reconciliation_view(
        proposals=report.proposals, entities=registry.list_entities(), observations=rows
    )
    assert view.items[0].status == "Needs Review"
    assert view.items[0].canonical_name == "Payments"
    assert not report.bindings


def test_conflict_shows_both_values_without_binding_or_resolution():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    canonical = _entity(
        registry,
        context,
        EntityType.APPLICATION,
        "Checkout",
        "catalogue",
        "APP-001",
        prospect_id="prospect-1",
    )
    rows = (
        _observation(
            "catalogue", "APP-001", attributes={"application_id": "APP-001", "owner": "Alice"}
        ),
        _observation(
            "finance", "finance-1", attributes={"application_id": "APP-001", "owner": "Bob"}
        ),
    )
    report = GovernedIdentityReconciliationService(registry).reconcile(
        rows, context=context, activation=ReconciliationActivation()
    )
    view = build_reconciliation_view(
        proposals=report.proposals, entities=registry.list_entities(), observations=rows
    )
    item = view.items[0]
    assert item.canonical_id == canonical.canonical_id
    assert item.status == "Conflict"
    assert item.conflicts == (("Owner", (("Catalogue", "Alice"), ("Finance", "Bob"))),)
    assert not report.bindings


def test_cross_type_same_name_stays_visibly_distinct():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    app = _entity(registry, context, EntityType.APPLICATION, "Payments", "catalogue", "app")
    service = _entity(
        registry, context, EntityType.BUSINESS_SERVICE, "Payments", "catalogue", "service"
    )
    view = build_enterprise_context(registry.list_entities())
    assert app.canonical_id != service.canonical_id
    assert {(item.name, item.entity_type_label) for item in view.entities} == {
        ("Payments", "Application"),
        ("Payments", "Business Service"),
    }


def test_reconciliation_decision_wrappers_enforce_existing_operational_roles():
    context = TenantContext(ORG, TENANT)
    registry, _relationships = _service(context)
    canonical = _entity(registry, context, EntityType.APPLICATION, "Payments", "catalogue", "app")
    service = GovernedIdentityReconciliationService(registry)
    rows = (_observation("a", "1", name="Payments"), _observation("b", "2", name="Payments"))
    proposal = service.reconcile(
        rows, context=context, activation=ReconciliationActivation()
    ).proposals[0]
    for action in ("confirm", "reject"):
        try:
            if action == "confirm":
                confirm_reconciliation(
                    service,
                    proposal,
                    canonical_id=canonical.canonical_id,
                    authorization=_authorization("executive", "viewer"),
                    reason="reviewed",
                )
            else:
                reject_reconciliation(
                    service,
                    proposal,
                    authorization=_authorization("executive", "viewer"),
                    reason="reviewed",
                )
        except PermissionError:
            pass
        else:
            raise AssertionError("unauthorized reconciliation mutation was accepted")
    decision = confirm_reconciliation(
        service,
        proposal,
        canonical_id=canonical.canonical_id,
        authorization=_authorization("operations", "operator"),
        reason="reviewed authoritative records",
    )
    assert decision.candidate_canonical_id == canonical.canonical_id


def test_scope_filter_removes_other_prospect_entities():
    _context, registry, relationships, _report, _view = _controlled_context()
    first = build_enterprise_context(
        registry.list_entities(),
        relationships.search_relationships(organization_id="org-act006"),
        prospect_id="prospect-1",
    )
    second = build_enterprise_context(
        registry.list_entities(),
        relationships.search_relationships(organization_id="org-act006"),
        prospect_id="prospect-b",
    )
    assert first.entities
    assert not second.entities


def test_production_views_reconstruct_identically_after_durable_restart(tmp_path):
    _context, _registry, _relationships, _report, context_view = _controlled_context()
    _registry2, _resource, _report2, reconciliation_view = _matched_reconciliation()
    database = tmp_path / "act010b.db"
    scope = LifecycleScope("org", "tenant", "prospect", "analysis")
    first = SQLiteLifecycleRepository(database)
    persist_production_views(first, scope, context_view, reconciliation_view)
    second = SQLiteLifecycleRepository(database)
    restored = load_production_views(second, scope)
    assert restored == (context_view, reconciliation_view)


def test_configured_runtime_reloads_views_for_exact_admission_scope(tmp_path):
    from tests.universal_evidence.test_pue_governed_measurement_pilot import _admission

    admission = _admission()
    _context, _registry, _relationships, _report, context_view = _controlled_context()
    reconciliation_view = build_reconciliation_view()
    database = tmp_path / "configured.db"
    repository = SQLiteLifecycleRepository(database)
    scope = LifecycleScope(
        admission.scope.organization_id or "UNKNOWN",
        admission.scope.tenant_id or "UNKNOWN",
        admission.scope.prospect_id,
        admission.scope.analysis_id,
    )
    persist_production_views(repository, scope, context_view, reconciliation_view)
    assert load_configured_production_views(admission, database=database) == (
        context_view,
        reconciliation_view,
    )


def test_configured_runtime_without_materialization_is_safe_empty_state(tmp_path):
    from tests.universal_evidence.test_pue_governed_measurement_pilot import _admission

    assert (
        load_configured_production_views(_admission(), database=tmp_path / "empty.db")
        is None
    )


def test_live_view_uses_same_canonical_registry_and_relationship_ids(monkeypatch):
    from types import SimpleNamespace

    context, registry, relationships, _report, expected = _controlled_context()

    class RelationshipFacade:
        def get_relationships(self, canonical_id):
            entity = registry.get_entity(canonical_id)
            return tuple(
                row
                for row in relationships.search_relationships(
                    organization_id=context.organization_id
                )
                if entity.id in (row.source_entity_id, row.target_entity_id)
            )

    monkeypatch.setattr(
        "services.enterprise_spend_composition.authenticated_tenant_context",
        lambda _session: SimpleNamespace(fabric_context=context),
    )
    monkeypatch.setattr(
        "services.enterprise_registry_composition.enterprise_registry_service",
        lambda _context, role: registry,
    )
    monkeypatch.setattr(
        "services.relationship_intelligence_composition.relationship_intelligence_service",
        lambda _context, role: RelationshipFacade(),
    )
    admission = SimpleNamespace(
        scope=SimpleNamespace(prospect_id="prospect-1", analysis_id="analysis-1")
    )
    actual, reconciliation = load_live_canonical_views({}, admission, role="operations")
    assert actual == expected
    assert {item.canonical_id for item in actual.entities} == {
        item.canonical_id for item in registry.list_entities()
    }
    assert not reconciliation.items


def test_cur_financial_evidence_has_no_fabricated_entity_or_reconciliation():
    # CUR discovery alone produces no ACT-006 entities and no ACT-007 cross-source authority.
    context = build_enterprise_context(())
    reconciliation = build_reconciliation_view()
    assert context.entities == ()
    assert reconciliation.items == ()
    assert reconciliation.source_count == 0
