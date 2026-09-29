from dataclasses import dataclass

from universal_evidence.pilot.evidence_package_governance import (
    govern_certified_package_source,
)


@dataclass(frozen=True)
class FakeCandidate:
    semantic_concept_id: str


@dataclass(frozen=True)
class FakeColumn:
    original_header: str
    source_column_reference: str
    candidates: tuple[FakeCandidate, ...] = ()


@dataclass(frozen=True)
class FakeDiscovery:
    columns: tuple[FakeColumn, ...]


class FakeConfirmationState:
    value = "REQUIRED"


class FakeConfirmationRequirement:
    state = FakeConfirmationState()


class FakeConfirmationService:
    def get_effective_mapping(self, column, *, actor):
        return None

    def evaluate_confirmation_requirement(self, column):
        return FakeConfirmationRequirement()


class FakeSemanticService:
    def __init__(self, columns):
        self._discovery = FakeDiscovery(tuple(columns))
        self.calls = []
        self.confirmation_service = FakeConfirmationService()

    def discovery(self, admission):
        return self._discovery

    def confirm(
        self,
        admission,
        column_reference,
        concept_id,
        *,
        actor,
    ):
        self.calls.append(
            (
                admission,
                column_reference,
                concept_id,
                actor,
            )
        )
        return {
            "column_reference": column_reference,
            "concept_id": concept_id,
            "action": "confirm",
        }

    def override(
        self,
        admission,
        column_reference,
        concept_id,
        *,
        actor,
        reason,
    ):
        self.calls.append(
            (
                admission,
                column_reference,
                concept_id,
                actor,
            )
        )
        return {
            "column_reference": column_reference,
            "concept_id": concept_id,
            "action": "override",
            "reason": reason,
        }


def test_inventory_certified_fields_flow_through_confirm():
    admission = object()
    actor = object()

    semantic = FakeSemanticService(
        (
            FakeColumn("ResourceId", "inventory:ResourceId"),
            FakeColumn("ResourceType", "inventory:ResourceType"),
            FakeColumn("AccountId", "inventory:AccountId"),
            FakeColumn("Region", "inventory:Region"),
            FakeColumn("Application", "inventory:Application"),
            FakeColumn("Environment", "inventory:Environment"),
            FakeColumn("Owner", "inventory:Owner"),
            FakeColumn("CostCenter", "inventory:CostCenter"),
            FakeColumn("BU", "inventory:BU"),
            FakeColumn("State", "inventory:State"),
        )
    )

    result = govern_certified_package_source(
        admission=admission,
        source_type="inventory",
        semantic_service=semantic,
        actor=actor,
    )

    assert result.confirmed_count == 9
    assert result.skipped_count == 1

    actual = {
        (column_reference, concept_id) for _, column_reference, concept_id, _ in semantic.calls
    }

    assert actual == {
        ("inventory:ResourceId", "resource.identifier"),
        ("inventory:ResourceType", "resource.type"),
        ("inventory:AccountId", "cloud.account"),
        ("inventory:Region", "cloud.region"),
        ("inventory:Application", "application.name"),
        ("inventory:Environment", "tagging.environment"),
        ("inventory:Owner", "ownership.owner"),
        ("inventory:CostCenter", "organization.cost_center"),
        ("inventory:BU", "organization.business_unit"),
    }


def test_cost_certified_fields_flow_through_confirm():
    admission = object()
    actor = object()

    semantic = FakeSemanticService(
        (
            FakeColumn("BillingPeriodStart", "cost:BillingPeriodStart"),
            FakeColumn("UsageAccountId", "cost:UsageAccountId"),
            FakeColumn("UsageDate", "cost:UsageDate"),
            FakeColumn("ProductCode", "cost:ProductCode"),
            FakeColumn("UsageType", "cost:UsageType"),
            FakeColumn("ResourceId", "cost:ResourceId"),
            FakeColumn("UsageAmount", "cost:UsageAmount"),
            FakeColumn("UnblendedCost", "cost:UnblendedCost"),
            FakeColumn("Currency", "cost:Currency"),
            FakeColumn("Tag_Application", "cost:Tag_Application"),
            FakeColumn("Tag_Environment", "cost:Tag_Environment"),
            FakeColumn("Tag_CostCenter", "cost:Tag_CostCenter"),
        )
    )

    result = govern_certified_package_source(
        admission=admission,
        source_type="cost",
        semantic_service=semantic,
        actor=actor,
    )

    assert result.confirmed_count == 8
    assert result.skipped_count == 4

    actual = {
        (column_reference, concept_id) for _, column_reference, concept_id, _ in semantic.calls
    }

    assert actual == {
        ("cost:UsageAccountId", "cloud.account"),
        ("cost:ProductCode", "technology.service"),
        ("cost:ResourceId", "resource.identifier"),
        ("cost:UnblendedCost", "financial.cost.total"),
        ("cost:Currency", "financial.currency"),
        ("cost:Tag_Application", "application.name"),
        ("cost:Tag_Environment", "tagging.environment"),
        ("cost:Tag_CostCenter", "organization.cost_center"),
    }


def test_org_only_governs_supported_fields():
    semantic = FakeSemanticService(
        (
            FakeColumn("AccountId", "org:AccountId"),
            FakeColumn("AccountName", "org:AccountName"),
            FakeColumn("OrgUnit", "org:OrgUnit"),
            FakeColumn("Status", "org:Status"),
            FakeColumn("JoinedDate", "org:JoinedDate"),
        )
    )

    result = govern_certified_package_source(
        admission=object(),
        source_type="org",
        semantic_service=semantic,
        actor=object(),
    )

    assert result.confirmed_count == 2
    assert result.skipped_count == 3

    assert {
        (column_reference, concept_id) for _, column_reference, concept_id, _ in semantic.calls
    } == {
        ("org:AccountId", "cloud.account"),
        ("org:OrgUnit", "organization.business_unit"),
    }


def test_application_mapping_only_governs_supported_fields():
    semantic = FakeSemanticService(
        (
            FakeColumn("Application", "app:Application"),
            FakeColumn("BusinessService", "app:BusinessService"),
            FakeColumn("AccountId", "app:AccountId"),
            FakeColumn("Criticality", "app:Criticality"),
            FakeColumn("OwnerEmail", "app:OwnerEmail"),
        )
    )

    result = govern_certified_package_source(
        admission=object(),
        source_type="application_mapping",
        semantic_service=semantic,
        actor=object(),
    )

    assert result.confirmed_count == 4
    assert result.skipped_count == 1

    assert {
        (column_reference, concept_id) for _, column_reference, concept_id, _ in semantic.calls
    } == {
        ("app:Application", "application.name"),
        ("app:BusinessService", "business.service"),
        ("app:AccountId", "cloud.account"),
        ("app:OwnerEmail", "ownership.owner"),
    }


def test_unknown_source_type_fails_closed_without_confirming():
    semantic = FakeSemanticService(
        (
            FakeColumn("ResourceId", "unknown:ResourceId"),
            FakeColumn("Currency", "unknown:Currency"),
        )
    )

    result = govern_certified_package_source(
        admission=object(),
        source_type="unknown",
        semantic_service=semantic,
        actor=object(),
    )

    assert result.confirmed_count == 0
    assert result.skipped_count == 2
    assert semantic.calls == []


def test_exact_field_matching_remains_case_sensitive():
    semantic = FakeSemanticService(
        (
            FakeColumn("resourceid", "inventory:resourceid"),
            FakeColumn("ResourceId", "inventory:ResourceId"),
        )
    )

    result = govern_certified_package_source(
        admission=object(),
        source_type="inventory",
        semantic_service=semantic,
        actor=object(),
    )

    assert result.confirmed_count == 1
    assert result.skipped_count == 1

    assert semantic.calls[0][1] == "inventory:ResourceId"
    assert semantic.calls[0][2] == "resource.identifier"


def test_bridge_returns_real_confirm_results_without_manufacturing_decisions():
    admission = object()
    actor = object()

    semantic = FakeSemanticService((FakeColumn("Currency", "cost:Currency"),))

    result = govern_certified_package_source(
        admission=admission,
        source_type="cost",
        semantic_service=semantic,
        actor=actor,
    )

    assert result.confirmed_count == 1
    assert result.decisions == (
        {
            "column_reference": "cost:Currency",
            "concept_id": "financial.currency",
            "action": "override",
            "reason": "Certified evidence package contract: cost.Currency",
        },
    )


def test_candidate_match_uses_confirm_not_override():
    admission = object()
    actor = object()

    semantic = FakeSemanticService(
        (
            FakeColumn(
                "Currency",
                "cost:Currency",
                (FakeCandidate("financial.currency"),),
            ),
        )
    )

    result = govern_certified_package_source(
        admission=admission,
        source_type="cost",
        semantic_service=semantic,
        actor=actor,
    )

    assert result.confirmed_count == 1
    assert result.decisions[0]["action"] == "confirm"


def test_certified_non_candidate_uses_governed_override():
    admission = object()
    actor = object()

    semantic = FakeSemanticService(
        (
            FakeColumn(
                "ProductCode",
                "cost:ProductCode",
                (),
            ),
        )
    )

    result = govern_certified_package_source(
        admission=admission,
        source_type="cost",
        semantic_service=semantic,
        actor=actor,
    )

    assert result.confirmed_count == 1
    assert result.decisions[0]["action"] == "override"
    assert result.decisions[0]["concept_id"] == "technology.service"
    assert result.decisions[0]["reason"] == "Certified evidence package contract: cost.ProductCode"


def test_candidate_not_requiring_confirmation_uses_certified_override():
    admission = object()
    actor = object()

    semantic = FakeSemanticService(
        (
            FakeColumn(
                "ResourceId",
                "inventory:ResourceId",
                (FakeCandidate("resource.identifier"),),
            ),
        )
    )

    class NotRequiredState:
        value = "NOT_REQUIRED"

    class NotRequiredRequirement:
        state = NotRequiredState()

    semantic.confirmation_service.evaluate_confirmation_requirement = (
        lambda column: NotRequiredRequirement()
    )

    result = govern_certified_package_source(
        admission=admission,
        source_type="inventory",
        semantic_service=semantic,
        actor=actor,
    )

    assert result.confirmed_count == 1
    assert result.decisions[0]["action"] == "override"
    assert result.decisions[0]["concept_id"] == "resource.identifier"
    assert (
        result.decisions[0]["reason"] == "Certified evidence package contract: inventory.ResourceId"
    )
