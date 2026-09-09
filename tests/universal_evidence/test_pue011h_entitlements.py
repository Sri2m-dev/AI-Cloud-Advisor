from __future__ import annotations

import io
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from openpyxl import Workbook

from universal_evidence.containers import decompose_xlsx
from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.entitlements import (
    EntitlementConcept,
    QuantityReconciliationState,
    SavingsEvidenceState,
    analyze_entitlement_evidence,
    assert_entitlement_scope,
)
from universal_evidence.semantics import classify_decomposition, group_evidence_sets


def analyze(workbook, tenant="tenant"):
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    context = EvidenceAnalysisContext("analysis", "source", "prospect", "org", tenant)
    decomposition = decompose_xlsx(
        context=context,
        content=stream.getvalue(),
        admitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_reference="authorized:synthetic",
        filename="neutral.xlsx",
    )
    classifications = classify_decomposition(decomposition)
    sets = group_evidence_sets(decomposition.regions, classifications)
    return analyze_entitlement_evidence(
        decomposition=decomposition,
        classifications=classifications,
        evidence_sets=sets,
        content=stream.getvalue(),
    )


def license_workbook(*, purchased=3, duplicate=False, summary_assigned=2):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "License Assignments"
    sheet.append(["Assigned To", "Email", "License Tier", "Status", "Assigned Date"])
    sheet.append(["User A", "a@example.com", "Business", "Assigned", "2026-01-01"])
    sheet.append(["User B", "b@example.com", "Business", "Assigned", "2026-01-01"])
    if duplicate:
        sheet.append(["User A", "a@example.com", "Business", "Assigned", "2026-01-01"])
    sheet.append(["(unassigned)", None, "Business", "Unused", None])
    sheet.append([])
    sheet.append(["Licenses Purchased", purchased])
    sheet.append(["Assigned", summary_assigned])
    sheet.append(["Unused", 1])
    return workbook


def test_purchased_assigned_and_unassigned_reconcile_without_savings():
    result = analyze(license_workbook())
    assert (result.purchased_license_quantity, result.assigned_license_quantity) == (3, 2)
    assert result.unassigned_license_quantity == 1
    assert result.assignment_utilization_percent == Decimal("66.67")
    assert result.activity_utilization_percent is None
    assert result.reconciliations[0].state is QuantityReconciliationState.RECONCILED
    assert result.savings_state is SavingsEvidenceState.INSUFFICIENT_EVIDENCE
    assert result.savings_amount is None


def test_access_only_does_not_create_paid_license_quantity():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "IAM Console Access"
    sheet.append(["User", "Email", "Console Access", "Role", "Status"])
    sheet.append(["A", "a@example.com", "Enabled", "Admin", "Assigned"])
    result = analyze(workbook)
    assert result.access_entitlement_quantity == 1
    assert result.purchased_license_quantity == result.assigned_license_quantity == 0
    assert result.observations[0].concept is EntitlementConcept.ACCESS_ENTITLEMENT


def test_duplicate_stable_account_row_is_not_double_counted():
    result = analyze(license_workbook(duplicate=True))
    assert result.assigned_license_quantity == 2
    assert len(result.observations) == 3


def test_summary_detail_mismatch_is_preserved():
    result = analyze(license_workbook(summary_assigned=1))
    assert result.reconciliations[0].state is QuantityReconciliationState.MISMATCH
    assert result.assignment_utilization_percent is None


def test_department_is_context_not_owner_or_cost_center():
    workbook = license_workbook()
    workbook["License Assignments"]["F1"] = "Department"
    workbook["License Assignments"]["F2"] = "Operations"
    result = analyze(workbook)
    assert result.observations[0].department_context == "Operations"
    assert not hasattr(result.observations[0], "owner")
    assert not hasattr(result.observations[0], "cost_center")


def test_foreign_tenant_reconciliation_is_forbidden():
    left = analyze(license_workbook(), "tenant-a")
    right = analyze(license_workbook(), "tenant-b")
    with pytest.raises(PermissionError):
        assert_entitlement_scope(left, right)
