from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

from universal_evidence.pilot.evidence_package_runtime import (
    CertifiedPackageSource,
)


@dataclass(frozen=True)
class PackageFinding:
    code: str
    severity: str
    source_type: str
    source_identifier: str
    evidence_reference: str
    message: str
    billing_period: str | None = None


@dataclass(frozen=True)
class PackageSourceCoverage:
    source_type: str
    observed_rows: int
    governed_fields: int
    certified_fields: int


@dataclass(frozen=True)
class EvidencePackageIntelligence:
    findings: tuple[PackageFinding, ...]
    source_coverage: tuple[PackageSourceCoverage, ...]
    organization_accounts: tuple[str, ...]
    inventory_resources: tuple[str, ...]
    cost_resources: tuple[str, ...]
    applications: tuple[str, ...]
    billing_periods: tuple[str, ...]
    governed_cost: Decimal | None
    currencies: tuple[str, ...]


_CERTIFIED_FIELDS = {
    "org": frozenset(
        {
            "AccountId",
            "OrgUnit",
        }
    ),
    "inventory": frozenset(
        {
            "ResourceId",
            "ResourceType",
            "AccountId",
            "Region",
            "Application",
            "Environment",
            "Owner",
            "CostCenter",
            "BU",
        }
    ),
    "cost": frozenset(
        {
            "UsageAccountId",
            "ProductCode",
            "ResourceId",
            "UnblendedCost",
            "Currency",
            "Tag_Application",
            "Tag_Environment",
            "Tag_CostCenter",
        }
    ),
    "application_mapping": frozenset(
        {
            "Application",
            "BusinessService",
            "AccountId",
            "OwnerEmail",
        }
    ),
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _identifier(
    source_type: str,
    row: Mapping[str, Any],
    ordinal: int,
) -> str:
    candidates = {
        "org": ("AccountId",),
        "inventory": ("ResourceId",),
        "cost": ("ResourceId", "UsageAccountId"),
        "application_mapping": ("Application",),
    }[source_type]

    for field in candidates:
        value = _text(row.get(field))
        if value:
            return value

    return f"row:{ordinal}"


def _formula_like(value) -> bool:
    text = _text(value).lstrip()
    return bool(text) and text[0] in ("=", "+", "-", "@")


def _row_has_formula_like_values(row, fields) -> bool:
    return any(_formula_like(row.get(field)) for field in fields)


def _finding(
    *,
    code: str,
    severity: str,
    source_type: str,
    source_identifier: str,
    file_id: str,
    ordinal: int,
    message: str,
) -> PackageFinding:
    return PackageFinding(
        code=code,
        severity=severity,
        source_type=source_type,
        source_identifier=source_identifier,
        evidence_reference=f"file:{file_id}:row:{ordinal}",
        message=message,
    )


def assess_certified_evidence_package(
    sources: Iterable[CertifiedPackageSource],
    *,
    package_period: Mapping[str, Any] | None = None,
) -> EvidencePackageIntelligence:
    expected_months = _expected_months(package_period)
    source_list = tuple(sources)

    by_type = {source.source_type: source for source in source_list}

    required = {
        "org",
        "inventory",
        "cost",
        "application_mapping",
    }

    missing = required - set(by_type)
    if missing:
        raise ValueError(
            "Certified evidence package is missing source types: " + ", ".join(sorted(missing))
        )

    findings: list[PackageFinding] = []

    org_accounts: set[str] = set()
    suspended_accounts: set[str] = set()

    inventory_resources: set[str] = set()
    inventory_accounts: set[str] = set()
    sanitisation_resources: set[str] = set()

    cost_resources: set[str] = set()
    cost_accounts: set[str] = set()

    applications: set[str] = set()
    application_accounts: set[str] = set()

    billing_periods: set[str] = set()
    account_periods: dict[str, set[str]] = {}
    account_rows: dict[str, int] = {}
    currencies: set[str] = set()

    governed_cost = Decimal("0")
    governed_cost_seen = False

    org_source = by_type["org"]
    for ordinal, row in enumerate(
        org_source.rows,
        start=1,
    ):
        account = _text(row.get("AccountId"))
        if account:
            org_accounts.add(account)

        status = _text(row.get("Status")).upper()
        if account and status == "SUSPENDED":
            suspended_accounts.add(account)
            findings.append(
                _finding(
                    code="SUSPENDED_ORGANIZATION_ACCOUNT",
                    severity="warning",
                    source_type="org",
                    source_identifier=account,
                    file_id=org_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Organization evidence identifies this " "cloud account as suspended."
                    ),
                )
            )

    inventory_source = by_type["inventory"]
    for ordinal, row in enumerate(
        inventory_source.rows,
        start=1,
    ):
        resource = _text(row.get("ResourceId"))
        account = _text(row.get("AccountId"))

        if resource:
            inventory_resources.add(resource)

        if account:
            inventory_accounts.add(account)

        owner = _text(row.get("Owner"))
        if owner and "@" in owner and not _formula_like(owner):
            findings.append(
                _finding(
                    code="PERSONAL_DATA_PRESENT",
                    severity="info",
                    source_type="inventory",
                    source_identifier=resource or account,
                    file_id=inventory_source.file_id,
                    ordinal=ordinal,
                    message=("Owner tags contain email addresses; "
                             "apply governed personal-data handling."),
                )
            )

        sanitisation_fields = (
            "Application",
            "Environment",
            "Owner",
            "CostCenter",
            "BU",
        )

        if resource and _row_has_formula_like_values(
            row,
            sanitisation_fields,
        ):
            sanitisation_resources.add(resource)
            findings.append(
                _finding(
                    code="SANITISATION_REQUIRED",
                    severity="warning",
                    source_type="inventory",
                    source_identifier=resource,
                    file_id=inventory_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Inventory evidence contains a formula-like "
                        "classification value and requires governed "
                        "sanitisation before ordinary classification."
                    ),
                )
            )

        if account and account not in org_accounts:
            findings.append(
                _finding(
                    code="INVENTORY_ACCOUNT_NOT_IN_ORGANIZATION",
                    severity="warning",
                    source_type="inventory",
                    source_identifier=resource or account,
                    file_id=inventory_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Inventory references an account that is "
                        "not present in organization evidence."
                    ),
                )
            )

        tag_fields = (
            "Application",
            "Environment",
            "Owner",
            "CostCenter",
            "BU",
        )

        if resource and any(not _text(row.get(field)) for field in tag_fields):
            findings.append(
                _finding(
                    code="INCOMPLETE_RESOURCE_CLASSIFICATION",
                    severity="info",
                    source_type="inventory",
                    source_identifier=resource,
                    file_id=inventory_source.file_id,
                    ordinal=ordinal,
                    message=("Resource classification evidence is " "incomplete."),
                )
            )

    cost_source = by_type["cost"]
    for ordinal, row in enumerate(
        cost_source.rows,
        start=1,
    ):
        resource = _text(row.get("ResourceId"))
        account = _text(row.get("UsageAccountId"))
        period = _text(row.get("BillingPeriodStart"))
        currency = _text(row.get("Currency")).upper()
        raw_cost = _text(row.get("UnblendedCost"))

        if resource:
            cost_resources.add(resource)

        if account:
            cost_accounts.add(account)

        if period:
            billing_periods.add(period[:7])
            if account:
                try:
                    month = date.fromisoformat(period).replace(day=1).isoformat()
                except ValueError as exc:
                    raise ValueError("Invalid BillingPeriodStart in cost evidence") from exc
                account_periods.setdefault(account, set()).add(month)
        if account:
            account_rows.setdefault(account, ordinal)

        if currency:
            currencies.add(currency)

        if raw_cost:
            try:
                governed_cost += Decimal(raw_cost)
                governed_cost_seen = True
            except InvalidOperation:
                findings.append(
                    _finding(
                        code="INVALID_COST_VALUE",
                        severity="warning",
                        source_type="cost",
                        source_identifier=resource or account,
                        file_id=cost_source.file_id,
                        ordinal=ordinal,
                        message=("Cost evidence could not be interpreted " "as a monetary value."),
                    )
                )

        if account and account not in org_accounts:
            findings.append(
                _finding(
                    code="COST_ACCOUNT_NOT_IN_ORGANIZATION",
                    severity="warning",
                    source_type="cost",
                    source_identifier=account,
                    file_id=cost_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Cost evidence references an account that "
                        "is not present in organization evidence."
                    ),
                )
            )

        if resource and resource not in inventory_resources:
            findings.append(
                _finding(
                    code="COST_RESOURCE_NOT_IN_INVENTORY",
                    severity="warning",
                    source_type="cost",
                    source_identifier=resource,
                    file_id=cost_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Cost evidence references a resource that "
                        "is not present in inventory evidence."
                    ),
                )
            )

        classification = (
            _text(row.get("Tag_Application")),
            _text(row.get("Tag_Environment")),
            _text(row.get("Tag_CostCenter")),
        )

        if (
            resource
            and resource in inventory_resources
            and any(not value for value in classification)
        ):
            findings.append(
                _finding(
                    code="UNTAGGED_COST_RESOURCE",
                    severity="info",
                    source_type="cost",
                    source_identifier=resource,
                    file_id=cost_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Cost resource is missing one or more " "governed classification tags."
                    ),
                )
            )

    # Only accounts with cost evidence establish a billing obligation. An org
    # account alone (including a suspended account) does not establish one.
    for account in sorted(cost_accounts):
        for month in sorted(expected_months - account_periods.get(account, set())):
            findings.append(
                PackageFinding(
                    code="MISSING_COST_PERIOD",
                    severity="warning",
                    source_type="cost",
                    source_identifier=account,
                    evidence_reference=(
                        f"file:{cost_source.file_id}:row:{account_rows[account]}" ";manifest:period"
                    ),
                    message=f"Account cost evidence is missing declared billing month {month}.",
                    billing_period=month,
                )
            )

    cost_source_resource_ids = {
        _text(row.get("ResourceId")) for row in cost_source.rows if _text(row.get("ResourceId"))
    }

    for ordinal, row in enumerate(
        inventory_source.rows,
        start=1,
    ):
        resource = _text(row.get("ResourceId"))

        if (
            resource
            and resource not in cost_source_resource_ids
            and resource not in sanitisation_resources
        ):
            findings.append(
                _finding(
                    code="INVENTORY_RESOURCE_WITHOUT_COST",
                    severity="info",
                    source_type="inventory",
                    source_identifier=resource,
                    file_id=inventory_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Inventory resource has no matching resource "
                        "identifier in cost evidence."
                    ),
                )
            )

    app_source = by_type["application_mapping"]
    for ordinal, row in enumerate(
        app_source.rows,
        start=1,
    ):
        application = _text(row.get("Application"))
        account = _text(row.get("AccountId"))

        if application:
            applications.add(application)

        if account:
            application_accounts.add(account)

        if account and account not in org_accounts:
            findings.append(
                _finding(
                    code="APPLICATION_ACCOUNT_NOT_IN_ORGANIZATION",
                    severity="warning",
                    source_type="application_mapping",
                    source_identifier=account,
                    file_id=app_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Application mapping references an account "
                        "that is not present in organization evidence."
                    ),
                )
            )

        owner = _text(row.get("OwnerEmail"))
        if owner and "@" in owner:
            findings.append(
                _finding(
                    code="PERSONAL_DATA_PRESENT",
                    severity="info",
                    source_type="application_mapping",
                    source_identifier=application or account,
                    file_id=app_source.file_id,
                    ordinal=ordinal,
                    message=(
                        "Owner evidence contains an email address; "
                        "apply governed personal-data handling."
                    ),
                )
            )

    source_coverage = []

    for source in source_list:
        certified = _CERTIFIED_FIELDS[source.source_type]

        observed_fields = {
            field for row in source.rows for field in certified if _text(row.get(field))
        }

        source_coverage.append(
            PackageSourceCoverage(
                source_type=source.source_type,
                observed_rows=len(source.rows),
                governed_fields=len(observed_fields),
                certified_fields=len(certified),
            )
        )

    return EvidencePackageIntelligence(
        findings=tuple(findings),
        source_coverage=tuple(source_coverage),
        organization_accounts=tuple(sorted(org_accounts)),
        inventory_resources=tuple(sorted(inventory_resources)),
        cost_resources=tuple(sorted(cost_resources)),
        applications=tuple(sorted(applications)),
        billing_periods=tuple(sorted(billing_periods)),
        governed_cost=(governed_cost if governed_cost_seen and len(currencies) == 1 else None),
        currencies=tuple(sorted(currencies)),
    )


def _expected_months(period: Mapping[str, Any] | None) -> set[str]:
    if period is None:
        return set()
    try:
        start = date.fromisoformat(period["start"])
        end = date.fromisoformat(period["end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Package period requires ISO start and end dates") from exc
    if end < start:
        raise ValueError("Package period end precedes start")
    first = start.year * 12 + start.month - 1
    last = end.year * 12 + end.month - 1
    return {date(index // 12, index % 12 + 1, 1).isoformat() for index in range(first, last + 1)}
