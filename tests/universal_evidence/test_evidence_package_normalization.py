"""Certified evidence-package governance -> normalization integration."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

from openpyxl import Workbook

from services.prospect_data_intake_service import ProspectTenant
from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationResolver,
    PueActivationService,
    ScopeLevel,
)
from universal_evidence.governance import (
    ActorType,
    ConfirmationActor,
    ConfirmationService,
)
from universal_evidence.pilot import admit_uploaded_evidence
from universal_evidence.pilot.evidence_package_governance import (
    govern_certified_package_source,
)
from universal_evidence.pilot.normalization_service import (
    PilotGovernedNormalizationService,
)
from universal_evidence.pilot.semantic_service import (
    PilotSemanticGovernanceService,
)
from universal_evidence.pilot.telemetry import InMemoryPilotTelemetry

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


COST_HEADERS = (
    "BillingPeriodStart",
    "UsageAccountId",
    "UsageDate",
    "ProductCode",
    "UsageType",
    "ResourceId",
    "UsageAmount",
    "UnblendedCost",
    "Currency",
    "Tag_Application",
    "Tag_Environment",
    "Tag_CostCenter",
)


def _cost_content():
    workbook = Workbook()
    sheet = workbook.active

    sheet.append(COST_HEADERS)

    sheet.append(
        (
            "2026-07-01",
            "111111111111",
            "2026-07-03",
            "AmazonEC2",
            "BoxUsage",
            "i-001",
            "10",
            "12.50",
            "USD",
            "Checkout",
            "prod",
            "CC-1001",
        )
    )

    sheet.append(
        (
            "2026-07-01",
            "111111111111",
            "2026-07-04",
            "AmazonS3",
            "TimedStorage",
            "bucket-001",
            "20",
            "7.25",
            "USD",
            "Checkout",
            "prod",
            "CC-1001",
        )
    )

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _admission():
    tenant = ProspectTenant(
        "clr-001b-04c-03c",
        "audit-clr-001b-04c-03c",
        NOW.isoformat(),
        (NOW + timedelta(days=30)).isoformat(),
        30,
    )

    return admit_uploaded_evidence(
        tenant,
        filename="cost_export.xlsx",
        content=_cost_content(),
        now=NOW,
    )


def _runtime(admission):
    repository = InMemoryPueActivationRepository()
    audit = InMemoryActivationAuditSink()

    activation = PueActivationService(
        repository=repository,
        audit_sink=audit,
        clock=lambda: NOW,
    )

    resolver = PueActivationResolver(
        repository=repository,
        clock=lambda: NOW,
    )

    admin = ActivationActor(
        "admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
            ActivationPermission.TRIGGER_PUE_ROLLBACK,
        ),
    )

    scope = ActivationScope(
        ScopeLevel.ANALYSIS,
        analysis_id=admission.scope.analysis_id,
        prospect_id=admission.scope.prospect_id,
    )

    activation.configure(
        scope=scope,
        stage=ActivationStage.CAPABILITY_VISIBLE,
        actor=admin,
        reason="CLR-001B-04C-03C integration test",
    )

    confirmation = ConfirmationService(clock=lambda: NOW)
    telemetry = InMemoryPilotTelemetry()

    semantic = PilotSemanticGovernanceService(
        activation_resolver=resolver,
        confirmation_service=confirmation,
        telemetry=telemetry,
    )

    normalization = PilotGovernedNormalizationService(
        activation_resolver=resolver,
        semantic_service=semantic,
        confirmation_service=confirmation,
        telemetry=telemetry,
    )

    actor = ConfirmationActor(
        "package-governor",
        "package-governor",
        "super_admin",
        ActorType.HUMAN,
    )

    return semantic, normalization, confirmation, actor


def _effective_concepts(semantic, confirmation, admission, actor):
    discovery = semantic.discovery(admission)

    result = {}

    for column in discovery.columns:
        effective = confirmation.get_effective_mapping(
            column,
            actor=actor,
        )

        if effective is not None:
            result[column.original_header] = effective.semantic_concept_id

    return result


def test_certified_cost_package_reaches_real_governed_normalization():
    admission = _admission()

    semantic, normalization, confirmation, actor = _runtime(admission)

    governed = govern_certified_package_source(
        admission=admission,
        source_type="cost",
        semantic_service=semantic,
        actor=actor,
    )

    assert governed.confirmed_count == 8
    assert governed.skipped_count == 4

    effective = _effective_concepts(
        semantic,
        confirmation,
        admission,
        actor,
    )

    assert effective == {
        "UsageAccountId": "cloud.account",
        "ProductCode": "technology.service",
        "ResourceId": "resource.identifier",
        "UnblendedCost": "financial.cost.total",
        "Currency": "financial.currency",
        "Tag_Application": "application.name",
        "Tag_Environment": "tagging.environment",
        "Tag_CostCenter": "organization.cost_center",
    }

    assert "BillingPeriodStart" not in effective
    assert "UsageDate" not in effective
    assert "UsageType" not in effective
    assert "UsageAmount" not in effective

    runs = normalization.execute(
        admission,
        actor=actor,
    )

    assert runs

    by_concept = {run.records[0].semantic_concept_id: run for run in runs if run.records}

    assert "financial.cost.total" in by_concept
    assert "financial.currency" in by_concept

    cost_run = by_concept["financial.cost.total"]
    currency_run = by_concept["financial.currency"]

    assert cost_run.processed_count == 2
    assert currency_run.processed_count == 2

    assert tuple(str(record.normalized_value) for record in cost_run.records) == (
        "12.50",
        "7.25",
    )

    assert tuple(record.normalized_value for record in currency_run.records) == (
        "USD",
        "USD",
    )

    assert tuple(record.source_value for record in cost_run.records) == (
        "12.50",
        "7.25",
    )


def test_repeated_certified_governance_is_idempotent():
    admission = _admission()

    semantic, normalization, confirmation, actor = _runtime(admission)

    first = govern_certified_package_source(
        admission=admission,
        source_type="cost",
        semantic_service=semantic,
        actor=actor,
    )

    second = govern_certified_package_source(
        admission=admission,
        source_type="cost",
        semantic_service=semantic,
        actor=actor,
    )

    assert first.confirmed_count == 8
    assert second.confirmed_count == 8

    discovery = semantic.discovery(admission)

    governed_columns = 0

    for column in discovery.columns:
        effective = confirmation.get_effective_mapping(
            column,
            actor=actor,
        )

        if effective is None:
            continue

        governed_columns += 1

        history = confirmation.get_decision_history(
            column,
            actor=actor,
        )

        assert len(history.decisions) == 1

    assert governed_columns == 8

    runs = normalization.execute(
        admission,
        actor=actor,
    )

    assert runs


def test_certified_package_sources_can_share_explicit_analysis_scope():
    tenant = ProspectTenant(
        "clr-package-shared-scope",
        "audit-clr-package-shared-scope",
        NOW.isoformat(),
        (NOW + timedelta(days=30)).isoformat(),
        30,
    )

    first = admit_uploaded_evidence(
        tenant,
        filename="first-cost.xlsx",
        content=_cost_content(),
        now=NOW,
        analysis_id="package-analysis-EVD-TEST",
    )

    second_content = _cost_content() + b"\n"

    second = admit_uploaded_evidence(
        tenant,
        filename="second-cost.xlsx",
        content=second_content,
        now=NOW,
        analysis_id="package-analysis-EVD-TEST",
    )

    assert first.scope.analysis_id == "package-analysis-EVD-TEST"
    assert second.scope.analysis_id == "package-analysis-EVD-TEST"

    assert first.scope.key == second.scope.key

    assert first.source_id != second.source_id
    assert first.file_id != second.file_id
    assert first.evidence_fingerprint != second.evidence_fingerprint
