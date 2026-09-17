"""Synthetic connector-to-intelligence reconciliation, without customer or live provider data."""

import json
import sqlite3
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from auth.authenticated_tenant import AuthenticatedTenantContext
from connector_adapters.live_cost import AWSLiveCostConnector, AzureLiveCostConnector
from connector_adapters.m365_discovery import M365DiscoveryConnector
from connector_registry.live_sources import LiveSourceRepository
from enterprise_copilot.composition import enterprise_ai_copilot
from enterprise_copilot.models import CopilotRequest
from enterprise_copilot.providers import ProviderResult
from services.enterprise_spend_composition import enterprise_spend_service
from services.financial_read_models import enterprise_spend_read_model
from services.governed_source_capabilities import GovernedSourceCapabilities
from services.live_source_service import LiveSourceService
from services.saas_discovery_intelligence_service import SaaSDiscoveryIntelligenceService


@pytest.fixture
def journey(tmp_path, monkeypatch):
    database = tmp_path / "governed.db"
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(database))
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    organization = str(uuid4())
    context = AuthenticatedTenantContext(
        organization,
        "Synthetic Customer",
        "synthetic@example.test",
        "synthetic@example.test",
        "client_admin",
        frozenset(),
        organization,
    )
    repo = LiveSourceRepository(database)
    user, sku, other_sku = str(uuid4()), str(uuid4()), str(uuid4())
    rows = {
        "aws": [
            {
                "start": "2026-09-01",
                "end": "2026-09-02",
                "service": "Compute",
                "amount": "100.25",
                "currency": "USD",
            }
        ],
        "azure": [
            {
                "start": "2026-09-01",
                "end": "2026-09-02",
                "service": "Storage",
                "amount": "49.75",
                "currency": "USD",
            }
        ],
        "m365": [
            {
                "entity_type": "license_sku",
                "sku_id": identifier,
                "sku_part_number": name,
                "total_units": 2,
                "consumed_units": 1,
                "suspended_units": 0,
            }
            for identifier, name in ((sku, "SPE_E5"), (other_sku, "ENTERPRISEPACK"))
        ]
        + [
            {
                "entity_type": "license_assignment",
                "user_id": user,
                "user_principal_name": "user@example.test",
                "sku_id": identifier,
                "assigned": True,
                "actively_used": False,
            }
            for identifier in (sku, other_sku)
        ]
        + [
            {
                "entity_type": "application",
                "external_id": str(uuid4()),
                "app_id": str(uuid4()),
                "display_name": "Synthetic Application",
                "publisher": None,
                "account_enabled": True,
            }
        ],
    }
    configurations = {
        "aws": {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/Test",
            "region": "us-east-1",
        },
        "azure": {
            "tenant_id": str(uuid4()),
            "subscription_id": str(uuid4()),
            "client_id": str(uuid4()),
        },
        "m365": {"tenant_id": str(uuid4()), "client_id": str(uuid4())},
    }

    def factory(provider, adapter):
        def create(config, credentials, now):
            connector = adapter(config, credentials, now=now)
            connector.authenticate = lambda: True
            connector.extract = lambda: rows[provider]
            return connector

        return create

    live = LiveSourceService(
        repo,
        factories={
            provider: factory(provider, adapter)
            for provider, adapter in (
                ("aws", AWSLiveCostConnector),
                ("azure", AzureLiveCostConnector),
                ("m365", M365DiscoveryConnector),
            )
        },
    )
    sources = {}
    for provider in rows:
        source = live.create(
            context,
            provider=provider,
            display_name="Synthetic " + provider,
            configuration=configurations[provider],
            secrets={} if provider == "aws" else {"client_secret": "synthetic-only"},
        )
        identifier = source["source_id"]
        assert live.validate_connection(context, identifier)["status"] == "READY"
        live.set_active(context, identifier, True)
        assert live.sync(context, identifier, request_key="initial")["status"] == "SUCCEEDED"
        sources[provider] = identifier
    return context, live, rows, sources


def test_cloud_cost_exact_reconciliation_and_executive_handoff(journey):
    context, live, _, _ = journey
    financial = enterprise_spend_service()
    facts = [
        fact
        for fact in live.repository.list_current_facts(context.organization_id, context.tenant_id)
        if fact.fact_type.value == "cloud_cost"
    ]
    source_total = sum(Decimal(fact.value["amount"]) for fact in facts)
    posture = financial.get_financial_posture(context)
    assert source_total == posture.cloud_spend == posture.total_ingested_spend == Decimal("150")
    assert {row["key"]: row["spend"] for row in financial.get_spend_by_provider(context)} == {
        "aws": Decimal("100.25"),
        "azure": Decimal("49.75"),
    }
    assert {row["key"]: row["spend"] for row in financial.get_spend_by_service(context)} == {
        "Compute": Decimal("100.25"),
        "Storage": Decimal("49.75"),
    }
    executive = enterprise_spend_read_model(replace(context, role="executive"), financial)
    assert executive.cloud.value == source_total
    assert executive.cloud.provenance
    assert executive.license.value is None and executive.saas.value is None
    assert all(
        row["source_instance_id"] and row["execution_id"] and row["lineage"]
        for row in financial.get_financial_evidence(context)
    )
    foreign_id = str(uuid4())
    foreign = replace(context, organization_id=foreign_id, tenant_id=foreign_id)
    assert not financial.get_financial_posture(foreign).has_data
    assert not financial.get_financial_evidence(foreign)
    assert not financial.get_financial_posture(context, (date(2026, 10, 1), None)).has_data


def test_cost_replay_correction_and_currency_fail_closed(journey):
    context, live, rows, sources = journey
    financial = enterprise_spend_service()
    assert financial.get_financial_posture(context).cloud_spend == Decimal("150")
    live.sync(context, sources["aws"], request_key="replay")
    assert financial.get_financial_posture(context).cloud_spend == Decimal("150")
    rows["aws"][0]["amount"] = "120.25"
    live.sync(context, sources["aws"], request_key="correction")
    assert financial.get_financial_posture(context).cloud_spend == Decimal("170")
    rows["azure"][0]["currency"] = "EUR"
    live.sync(context, sources["azure"], request_key="mixed")
    with pytest.raises(ValueError, match="Mixed currencies"):
        financial.get_financial_posture(context)


class Planner:
    name = "synthetic-semantic-provider"

    def __init__(self, capability, operation, filters=()):
        self.capability, self.operation, self.filters = capability, operation, filters
        self.questions = []
        self.generated_context = None

    def plan(self, *, question, catalogue, scope, conversation):
        self.questions.append(question)
        assert self.capability in {item.capability_id for item in catalogue}
        return {
            "interpretation": question,
            "entities": [],
            "measures": [],
            "dimensions": [],
            "filters": list(self.filters),
            "grouping": [],
            "synthesis": "Only cite governed evidence",
            "steps": [
                {
                    "step_id": "read",
                    "capability_id": self.capability,
                    "operation": self.operation,
                    "parameters": {},
                    "depends_on": [],
                }
            ],
        }

    def generate(self, *, system_prompt, context):
        self.generated_context = context
        return ProviderResult(json.dumps(context.evidence.facts, default=str))


def ask(journey, provider, question, *, context=None):
    tenant, live, _, _ = journey
    context = context or tenant

    def connection():
        db = sqlite3.connect(live.repository.database)
        db.row_factory = sqlite3.Row
        return db

    copilot = enterprise_ai_copilot(
        context.fabric_context,
        role=context.role,
        financial_context=context,
        providers={"synthetic": provider},
        environment="development",
        supabase_url="",
        supabase_key="",
        connection_factory=connection,
    )
    return copilot.ask(
        CopilotRequest(
            context.fabric_context,
            question,
            context.role,
            "synthetic-session",
            provider="synthetic",
        )
    )


@pytest.mark.parametrize(
    "capability,operation,questions",
    [
        (
            "microsoft_licenses",
            "LIST",
            ("What Microsoft licenses do we have?", "Show our M365 licence estate."),
        ),
        ("microsoft_assignments", "COUNT", ("How many users have E5?", "Who has Enterprise E5?")),
        (
            "microsoft_assignments",
            "MULTIPLE_LICENSES",
            (
                "Which users have multiple Microsoft licenses?",
                "Show people assigned several subscriptions.",
            ),
        ),
        (
            "microsoft_applications",
            "LIST",
            ("Which applications are registered?", "Show Entra applications."),
        ),
        (
            "source_execution",
            "LIST",
            ("When did AWS last sync?", "When was our Amazon billing source refreshed?"),
        ),
        (
            "cloud_financials",
            "BY_PROVIDER",
            ("Which cloud provider costs most?", "Compare provider spending."),
        ),
    ],
)
def test_semantic_capabilities_preserve_question_and_authority(
    journey, capability, operation, questions
):
    filters = (
        [{"dimension": "sku_part_number", "operator": "EQUALS", "value": "SPE_E5"}]
        if (capability == "microsoft_assignments" and operation == "COUNT")
        else ()
    )
    provider = Planner(capability, operation, filters)
    for question in questions:
        result = ask(journey, provider, question)
        assert not result.blocked and not result.unsupported
        assert result.citations
        assert provider.generated_context.evidence.facts
        if operation in {"COUNT", "MULTIPLE_LICENSES"}:
            assert provider.generated_context.evidence.facts[0]["count"] == 1
    assert provider.questions == list(questions)


@pytest.mark.parametrize(
    "capability,operation",
    [
        ("microsoft_assignments", "UNUSED"),
        ("microsoft_licenses", "COST"),
    ],
)
def test_absent_usage_and_license_cost_never_generate_a_conclusion(journey, capability, operation):
    provider = Planner(capability, operation)
    result = ask(journey, provider, "Explain this evidence boundary")
    assert result.answer.startswith("UNKNOWN") and result.unsupported
    assert provider.generated_context is None
    assert result.grounded_context.evidence.facts[0]["count"] is None


def test_failed_and_stale_sources_are_governed_capabilities(journey):
    context, live, rows, sources = journey
    past = datetime.now(timezone.utc) - timedelta(days=3)
    live.clock = lambda: past
    live.set_schedule(context, sources["aws"], enabled=True, cadence_seconds=3600)
    live.sync(context, sources["aws"], request_key="stale")
    rows["azure"][0]["amount"] = "invalid"
    assert live.sync(context, sources["azure"], request_key="failure")["status"] == "FAILED"
    provider = Planner(
        "source_health", "LIST", [{"dimension": "health", "operator": "EQUALS", "value": "FAILED"}]
    )
    result = ask(journey, provider, "What cloud feeds have errors?")
    records = result.grounded_context.evidence.facts[0]["records"]
    assert len(records) == 1 and records[0]["provider"] == "azure"
    assert "invalid" not in result.answer
    provider = Planner(
        "source_health", "LIST", [{"dimension": "health", "operator": "EQUALS", "value": "STALE"}]
    )
    result = ask(journey, provider, "Which connected feeds are overdue?")
    records = result.grounded_context.evidence.facts[0]["records"]
    assert len(records) == 1 and records[0]["provider"] == "aws"
    assert not result.unsupported


def test_partial_cost_period_is_not_silently_prorated(journey):
    context, live, rows, sources = journey
    rows["aws"][0]["end"] = "2026-10-01"
    live.sync(context, sources["aws"], request_key="long-period")
    with pytest.raises(ValueError, match="prorated"):
        enterprise_spend_service().get_financial_posture(
            context, (date(2026, 9, 1), date(2026, 9, 15))
        )
    with pytest.raises(ValueError, match="Overlapping"):
        enterprise_spend_service().get_financial_posture(context)


def test_same_tenant_upload_preserves_distinct_governed_authorities(journey):
    from services.prospect_data_intake_service import ProspectTenant
    from tests.universal_evidence.test_pue_governed_normalization_pilot import (
        NOW,
        _confirm,
        _content,
        _runtime,
    )
    from universal_evidence.pilot import admit_uploaded_evidence

    context, live, _, _ = journey
    tenant = ProspectTenant(
        context.tenant_id,
        "synthetic-upload",
        NOW.isoformat(),
        (NOW + timedelta(days=30)).isoformat(),
        30,
    )
    admission = admit_uploaded_evidence(
        tenant,
        filename="evidence.xlsx",
        content=_content(rows=(("Synthetic Upload", "7.25", "USD"),)),
        now=NOW,
        tenant_context=context,
    )
    assert admission.scope.organization_id == context.organization_id
    assert admission.scope.tenant_id == context.tenant_id
    normalization, semantic, *_tail, actor = _runtime(admission)
    _confirm(semantic, admission, actor, "Amount", "financial.cost.total")
    model = normalization.experience(admission, actor=actor)
    assert model.observation_count == 1 and model.quality.valid == 1
    assert enterprise_spend_service().get_financial_posture(context).cloud_spend == Decimal("150")
    assert SaaSDiscoveryIntelligenceService.snapshot(context, repository=live.repository)[
        "applications"
    ]


def test_capability_rejects_forged_tenant_and_sql_operation(journey):
    from enterprise_copilot.semantic_planner import SemanticPlanError

    context, live, _, _ = journey
    handler = GovernedSourceCapabilities(context, live=live).handlers()["cloud_financials"]
    arguments = dict(
        operation="TOTAL",
        parameters={},
        dependencies={},
        scope=context.fabric_context,
        constraints={"grouping": [], "filters": []},
    )
    foreign_id = str(uuid4())
    foreign = replace(context, organization_id=foreign_id, tenant_id=foreign_id)
    with pytest.raises(PermissionError):
        handler(**{**arguments, "scope": foreign.fabric_context})
    with pytest.raises(SemanticPlanError):
        handler(**{**arguments, "operation": "SELECT * FROM source_facts"})


def test_discovery_failure_preserves_evidence_without_false_zero(journey):
    context, live, _, sources = journey
    live.set_active(context, sources["m365"], False)
    snapshot = SaaSDiscoveryIntelligenceService.snapshot(context, repository=live.repository)
    assert snapshot["availability"] == "PARTIAL"
    assert snapshot["applications"][0]["publisher"] == "UNKNOWN"
    foreign_id = str(uuid4())
    foreign = replace(context, organization_id=foreign_id, tenant_id=foreign_id)
    result = ask(
        journey, Planner("microsoft_applications", "COUNT"), "Registered apps?", context=foreign
    )
    assert result.unsupported
    assert result.grounded_context.evidence.facts[0]["count"] is None
    for role in ("viewer", "technical"):
        with pytest.raises(PermissionError):
            GovernedSourceCapabilities(replace(context, role=role), live=live)
