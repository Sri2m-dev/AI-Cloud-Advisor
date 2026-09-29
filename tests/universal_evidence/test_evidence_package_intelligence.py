from decimal import Decimal

import pytest

from universal_evidence.pilot.evidence_package_intelligence import (
    assess_certified_evidence_package,
)
from universal_evidence.pilot.evidence_package_runtime import (
    CertifiedPackageSource,
)


def _sources():
    return (
        CertifiedPackageSource(
            source_type="org",
            file_id="org_accounts.csv",
            rows=(
                {
                    "AccountId": "111",
                    "AccountName": "Production",
                    "OrgUnit": "Retail",
                    "Status": "ACTIVE",
                },
                {
                    "AccountId": "222",
                    "AccountName": "Old",
                    "OrgUnit": "Retail",
                    "Status": "SUSPENDED",
                },
            ),
        ),
        CertifiedPackageSource(
            source_type="inventory",
            file_id="inventory.csv",
            rows=(
                {
                    "ResourceId": "i-shared",
                    "ResourceType": "EC2",
                    "AccountId": "111",
                    "Region": "ap-south-1",
                    "Application": "Checkout",
                    "Environment": "prod",
                    "Owner": "Platform",
                    "CostCenter": "CC100",
                    "BU": "Retail",
                },
                {
                    "ResourceId": "i-inventory-only",
                    "ResourceType": "EC2",
                    "AccountId": "111",
                    "Region": "ap-south-1",
                    "Application": "Checkout",
                    "Environment": "",
                    "Owner": "Platform",
                    "CostCenter": "CC100",
                    "BU": "Retail",
                },
            ),
        ),
        CertifiedPackageSource(
            source_type="cost",
            file_id="cost_export.csv",
            rows=(
                {
                    "BillingPeriodStart": "2026-01-01",
                    "UsageAccountId": "111",
                    "ProductCode": "AmazonEC2",
                    "ResourceId": "i-shared",
                    "UnblendedCost": "12.50",
                    "Currency": "USD",
                    "Tag_Application": "Checkout",
                    "Tag_Environment": "prod",
                    "Tag_CostCenter": "CC100",
                },
                {
                    "BillingPeriodStart": "2026-03-01",
                    "UsageAccountId": "999",
                    "ProductCode": "AmazonEC2",
                    "ResourceId": "i-cost-only",
                    "UnblendedCost": "7.25",
                    "Currency": "USD",
                    "Tag_Application": "",
                    "Tag_Environment": "prod",
                    "Tag_CostCenter": "",
                },
            ),
        ),
        CertifiedPackageSource(
            source_type="application_mapping",
            file_id="app_mapping.csv",
            rows=(
                {
                    "Application": "Checkout",
                    "BusinessService": "Order Processing",
                    "AccountId": "111",
                    "Criticality": "High",
                    "OwnerEmail": "owner@example.invalid",
                },
                {
                    "Application": "Unknown App",
                    "BusinessService": "Unknown Service",
                    "AccountId": "888",
                    "Criticality": "Medium",
                    "OwnerEmail": "",
                },
            ),
        ),
    )


def _codes(result):
    return {item.code for item in result.findings}


def test_cross_source_findings_are_derived_from_evidence():
    result = assess_certified_evidence_package(_sources())

    codes = _codes(result)

    assert "SUSPENDED_ORGANIZATION_ACCOUNT" in codes
    assert "INVENTORY_RESOURCE_WITHOUT_COST" in codes
    assert "COST_RESOURCE_NOT_IN_INVENTORY" in codes
    assert "COST_ACCOUNT_NOT_IN_ORGANIZATION" in codes
    assert "APPLICATION_ACCOUNT_NOT_IN_ORGANIZATION" in codes
    assert "INCOMPLETE_RESOURCE_CLASSIFICATION" in codes
    assert "PERSONAL_DATA_PRESENT" in codes


def test_account_integrity_findings_identify_the_account():
    result = assess_certified_evidence_package(_sources())

    cost = [
        finding for finding in result.findings if finding.code == "COST_ACCOUNT_NOT_IN_ORGANIZATION"
    ]

    application = [
        finding
        for finding in result.findings
        if finding.code == "APPLICATION_ACCOUNT_NOT_IN_ORGANIZATION"
    ]

    assert cost
    assert application

    assert all(finding.source_identifier == "999" for finding in cost)

    assert all(finding.source_identifier == "888" for finding in application)


def test_cost_resource_missing_from_inventory_is_not_also_untagged():
    result = assess_certified_evidence_package(_sources())

    missing_inventory = {
        finding.source_identifier
        for finding in result.findings
        if finding.code == "COST_RESOURCE_NOT_IN_INVENTORY"
    }

    untagged = {
        finding.source_identifier
        for finding in result.findings
        if finding.code == "UNTAGGED_COST_RESOURCE"
    }

    assert "i-cost-only" in missing_inventory
    assert "i-cost-only" not in untagged


def test_package_summary_is_evidence_derived():
    result = assess_certified_evidence_package(_sources())

    assert result.organization_accounts == (
        "111",
        "222",
    )
    assert result.inventory_resources == (
        "i-inventory-only",
        "i-shared",
    )
    assert result.cost_resources == (
        "i-cost-only",
        "i-shared",
    )
    assert result.applications == (
        "Checkout",
        "Unknown App",
    )
    assert result.billing_periods == (
        "2026-01",
        "2026-03",
    )
    assert result.governed_cost == Decimal("19.75")
    assert result.currencies == ("USD",)


def test_source_coverage_is_descriptive_not_authoritative_percentage():
    result = assess_certified_evidence_package(_sources())

    coverage = {item.source_type: item for item in result.source_coverage}

    assert coverage["org"].certified_fields == 2
    assert coverage["inventory"].certified_fields == 9
    assert coverage["cost"].certified_fields == 8
    assert coverage["application_mapping"].certified_fields == 4

    assert not hasattr(
        result,
        "evidence_coverage",
    )


def test_missing_certified_source_fails_closed():
    with pytest.raises(
        ValueError,
        match="missing source types",
    ):
        assess_certified_evidence_package(_sources()[:-1])


def test_expected_findings_oracle_is_not_a_runtime_input():
    result = assess_certified_evidence_package(_sources())

    assert not hasattr(
        result,
        "expected_findings",
    )


@pytest.mark.parametrize(
    "period",
    [
        {"start": "bad", "end": "2025-01-01"},
        {"start": "2026-01-01", "end": "2025-01-01"},
        {"start": "2025-01-01"},
    ],
)
def test_invalid_declared_period_fails_closed(period):
    with pytest.raises(ValueError, match="Package period"):
        assess_certified_evidence_package(_sources(), package_period=period)


def test_missing_periods_are_per_account_and_include_year_boundary():
    result = assess_certified_evidence_package(
        _sources(),
        package_period={"start": "2025-12-17", "end": "2026-03-09"},
    )
    missing = {
        (f.source_identifier, f.billing_period)
        for f in result.findings
        if f.code == "MISSING_COST_PERIOD"
    }
    assert missing == {
        ("111", "2025-12-01"),
        ("111", "2026-02-01"),
        ("111", "2026-03-01"),
        ("999", "2025-12-01"),
        ("999", "2026-01-01"),
        ("999", "2026-02-01"),
    }
    assert all(
        "manifest:period" in f.evidence_reference
        for f in result.findings
        if f.code == "MISSING_COST_PERIOD"
    )


def test_no_period_context_preserves_legacy_findings():
    assert "MISSING_COST_PERIOD" not in _codes(assess_certified_evidence_package(_sources()))


def test_mixed_currency_cost_remains_unknown():
    from dataclasses import replace

    sources = list(_sources())
    rows = list(sources[2].rows)
    rows[1] = dict(rows[1], Currency="EUR")
    sources[2] = replace(sources[2], rows=tuple(rows))
    assert assess_certified_evidence_package(sources).governed_cost is None
