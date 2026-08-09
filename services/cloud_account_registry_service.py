"""Governed cloud-account registry domain service."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping, Protocol

import pandas as pd

from auth.authenticated_tenant import AuthenticatedTenantContext
from repositories.cloud_account_registry_repository import CloudAccountRegistryRepository

PROVIDERS = {"aws", "azure", "gcp"}
READ_ROLES = {"super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"}
EDIT_ROLES = {"super_admin", "client_admin", "finance", "operations"}
FULL_ROLES = {"super_admin", "client_admin", "operations"}
RESOLVE_ROLES = {"super_admin", "client_admin", "organization_admin", "finance", "operations"}
APPROVE_ROLES = {"super_admin", "client_admin", "organization_admin"}
RESOLUTION_STATES = {
    "DISCOVERED",
    "PENDING_REVIEW",
    "PARTIALLY_MAPPED",
    "READY_FOR_APPROVAL",
    "APPROVED",
    "ACTIVE",
    "REJECTED",
    "SUSPENDED",
}
RESOLUTION_FIELDS = (
    "account_name",
    "alias",
    "environment",
    "business_unit",
    "department",
    "application",
    "business_service",
    "owner",
    "technical_owner",
    "finance_owner",
    "cost_center",
    "project_code",
    "criticality",
    "effective_date",
    "resolution_status",
)
IMPORT_COLUMNS = [
    "Provider",
    "Account ID",
    "Account Name",
    "Owner",
    "Business Unit",
    "Department",
    "Application",
    "Environment",
    "Budget",
]


class RegistryValidationError(ValueError):
    pass


class DiscoveredAccountSource(Protocol):
    def get_unknown_account_posture(
        self, context: AuthenticatedTenantContext
    ) -> tuple[Mapping[str, Any], ...]: ...

    def get_financial_posture(self, context: AuthenticatedTenantContext) -> Any: ...


class CloudAccountRegistryService:
    def __init__(
        self,
        repository: CloudAccountRegistryRepository,
        discovered_accounts: DiscoveredAccountSource | None = None,
    ) -> None:
        self.repository = repository
        self.discovered_accounts = discovered_accounts

    @staticmethod
    def permissions(context: AuthenticatedTenantContext) -> dict[str, bool]:
        return {
            "read": context.role in READ_ROLES,
            "edit": context.role in EDIT_ROLES,
            "full": context.role in FULL_ROLES,
            "resolve": context.role in RESOLVE_ROLES,
            "approve": context.role in APPROVE_ROLES,
        }

    @staticmethod
    def allocation_ready(values: Mapping[str, Any]) -> bool:
        return bool(
            values.get("owner")
            and (values.get("business_unit") or values.get("department"))
            and values.get("cost_center")
            and values.get("environment")
            and str(values.get("resolution_status") or "").upper() in {"APPROVED", "ACTIVE"}
        )

    def resolve_discovered(
        self,
        context: AuthenticatedTenantContext,
        discovered: Mapping[str, Any],
        values: Mapping[str, Any],
        *,
        reason: str,
        confirmed: bool,
        expected_state: str = "DISCOVERED",
    ):
        permissions = self.permissions(context)
        if not permissions["resolve"]:
            raise PermissionError("cloud account resolution denied")
        if not confirmed:
            raise RegistryValidationError("explicit resolution confirmation is required")
        if not str(reason or "").strip():
            raise RegistryValidationError("resolution reason is required")
        state = str(values.get("resolution_status") or "PENDING_REVIEW").upper()
        if state not in RESOLUTION_STATES:
            raise RegistryValidationError("invalid resolution status")
        if state in {"APPROVED", "ACTIVE"} and not permissions["approve"]:
            raise PermissionError("cloud account approval denied")
        evidence = discovered.get("source_evidence") or {}
        provider = str(
            discovered.get("provider") or evidence.get("original_provider") or "aws"
        ).lower()
        account_id = str(discovered.get("account_id") or "").strip()
        payer_id = str(
            discovered.get("payer_account_id") or evidence.get("payer_account_id") or ""
        ).strip()
        if provider != "aws" or not account_id or not payer_id:
            raise RegistryValidationError("immutable discovered AWS identity is required")
        mapping = {field: values.get(field) for field in RESOLUTION_FIELDS}
        mapping.update(
            source_import_id=discovered.get("source_import_id") or evidence.get("source_import_id"),
            first_seen_at=discovered.get("first_seen_at") or evidence.get("first_seen_at"),
            last_seen_at=discovered.get("last_seen_at") or evidence.get("last_seen_at"),
            billing_period=discovered.get("billing_period") or evidence.get("billing_period"),
            quarantined_spend=discovered.get("quarantined_spend")
            or evidence.get("quarantined_spend"),
            currency=discovered.get("currency") or evidence.get("currency"),
        )
        try:
            result = self.repository.resolve_account(
                context,
                discovered,
                mapping,
                reason=reason,
                confirmed=confirmed,
                expected_state=expected_state,
            )
        except AttributeError as exc:
            raise RuntimeError("account resolution repository is not configured") from exc
        if self.discovered_accounts is not None:
            self.discovered_accounts.invalidate(context.organization_id)
        return result

    def preview_bulk_resolution(self, context, accounts, shared_values):
        if not self.permissions(context)["resolve"]:
            raise PermissionError("bulk account resolution denied")
        selected = list(accounts)
        return {
            "accounts": selected,
            "count": len(selected),
            "quarantined_spend": sum(
                (float(row.get("quarantined_spend") or 0) for row in selected), 0.0
            ),
            "changes": {k: v for k, v in shared_values.items() if v not in (None, "")},
            "allocation_ready": all(
                self.allocation_ready({**row, **shared_values}) for row in selected
            ),
        }

    def commit_bulk_resolution(self, context, preview, *, reason: str, confirmed: bool):
        if not confirmed:
            raise RegistryValidationError("explicit bulk confirmation is required")
        if not str(reason or "").strip():
            raise RegistryValidationError("bulk resolution reason is required")
        if not preview.get("accounts"):
            raise RegistryValidationError("bulk accounts are required")
        return self.repository.bulk_resolve(
            context,
            preview["accounts"],
            preview.get("changes") or {},
            reason=reason,
            confirmed=confirmed,
        )

    @staticmethod
    def governance_score(row: Mapping[str, Any]) -> int:
        ownership = sum(bool(row.get(k)) for k in ("owner", "technical_owner", "finance_owner")) / 3
        mapping = (
            sum(
                bool(row.get(k))
                for k in (
                    "business_unit",
                    "department",
                    "application",
                    "business_service",
                    "cost_center",
                )
            )
            / 5
        )
        tags = max(0.0, min(1.0, float(row.get("tags_coverage") or 0) / 100))
        allocation = (
            1.0
            if row.get("cost_center")
            and float(row.get("monthly_budget") or row.get("budget") or 0) >= 0
            else 0.0
        )
        synced = row.get("last_synchronization")
        freshness = 1.0 if synced else 0.0
        return round(ownership * 30 + mapping * 25 + tags * 15 + allocation * 15 + freshness * 15)

    @staticmethod
    def governance_label(score: int) -> str:
        if score >= 95:
            return "Excellent"
        if score >= 85:
            return "Good"
        if score >= 70:
            return "Needs Improvement"
        return "Critical"

    def list_accounts(self, context: AuthenticatedTenantContext):
        if not self.permissions(context)["read"]:
            raise PermissionError("cloud account registry read denied")
        governed = [
            {
                **row,
                "record_origin": "governed_registry",
                "governance_assessed": True,
            }
            for row in self.repository.list_accounts(context)
        ]
        if self.discovered_accounts is None:
            return governed

        posture = self.discovered_accounts.get_financial_posture(context)
        discovered = self.discovered_accounts.get_unknown_account_posture(context)
        by_identity = {
            (str(row.get("provider") or "").lower(), str(row.get("account_id") or "")): row
            for row in governed
        }
        billing_period = (
            f"{posture.period_start.isoformat()} / {posture.period_end.isoformat()}"
            if posture.period_start and posture.period_end
            else None
        )
        for source_row in discovered:
            account_id = str(source_row.get("account_id") or "").strip()
            identity = ("aws", account_id)
            evidence = {
                "discovery_status": "discovered",
                "mapping_status": "unknown",
                "ownership_status": "unassigned",
                "lifecycle_status": "quarantined",
                "source": "aws_cur",
                "source_import_id": posture.latest_import_id,
                "payer_account_id": source_row.get("payer_account_id"),
                "first_seen_at": source_row.get("first_usage_at"),
                "last_seen_at": source_row.get("last_usage_at"),
                "billing_period": billing_period,
                "quarantined_spend": source_row.get("unblended_spend") or 0,
                "currency": source_row.get("currency") or posture.currency,
                "source_row_count": int(source_row.get("row_count") or 0),
                "governance_state": "Not assessed - pending mapping",
                "review_action": "Review / Map Account",
            }
            if identity in by_identity:
                by_identity[identity].update(evidence)
                continue
            by_identity[identity] = {
                "provider": "aws",
                "account_id": account_id,
                "account_name": account_id,
                "status": "pending_mapping",
                "record_origin": "financial_data_fabric_projection",
                "governance_score": None,
                "governance_assessed": False,
                **evidence,
            }
        return sorted(
            by_identity.values(),
            key=lambda row: (str(row.get("provider") or ""), str(row.get("account_id") or "")),
        )

    def dashboard(self, context: AuthenticatedTenantContext) -> dict[str, Any]:
        rows = self.list_accounts(context)
        posture = (
            self.discovered_accounts.get_financial_posture(context)
            if self.discovered_accounts is not None
            else None
        )
        scores = [int(r.get("governance_score") or 0) for r in rows if r.get("governance_assessed")]
        return {
            "accounts": rows,
            "total": len(rows),
            "aws": sum(r.get("provider") == "aws" for r in rows),
            "azure": sum(r.get("provider") == "azure" for r in rows),
            "gcp": sum(r.get("provider") == "gcp" for r in rows),
            "active": sum(r.get("status") == "active" for r in rows),
            "pending": sum(
                r.get("status") in {"pending", "pending_mapping"}
                or r.get("mapping_status") in {"unknown", "pending"}
                for r in rows
            ),
            "unknown": sum(
                r.get("mapping_status") == "unknown" or r.get("status") == "unknown" for r in rows
            ),
            "average_governance": round(sum(scores) / len(scores), 1) if scores else "Not assessed",
            "pending_review": sum(
                r.get("resolution_status") in {None, "DISCOVERED", "PENDING_REVIEW"} for r in rows
            ),
            "partially_mapped": sum(r.get("resolution_status") == "PARTIALLY_MAPPED" for r in rows),
            "ready_for_approval": sum(
                r.get("resolution_status") == "READY_FOR_APPROVAL" for r in rows
            ),
            "approved": sum(r.get("resolution_status") in {"APPROVED", "ACTIVE"} for r in rows),
            "quarantined_spend": getattr(posture, "quarantined_spend", 0),
            "resolved_spend": getattr(posture, "resolved_spend", 0),
            "allocation_coverage": getattr(posture, "allocation_coverage_percentage", 0),
        }

    def save(
        self,
        context: AuthenticatedTenantContext,
        values: Mapping[str, Any],
        *,
        registry_id: str | None = None,
        reason: str,
    ):
        if not self.permissions(context)["edit"]:
            raise PermissionError("cloud account registry edit denied")
        provider = str(values.get("provider") or "").strip().lower()
        account_id = str(values.get("account_id") or "").strip()
        if provider not in PROVIDERS:
            raise RegistryValidationError("provider must be AWS, Azure, or GCP")
        if not account_id:
            raise RegistryValidationError("account_id is required")
        if not str(reason or "").strip():
            raise RegistryValidationError("modification reason is required")
        existing = self.repository.list_accounts(context)
        if any(
            r.get("provider") == provider
            and r.get("account_id") == account_id
            and str(r.get("id")) != str(registry_id or "")
            for r in existing
        ):
            raise RegistryValidationError(f"duplicate {provider} account identity")
        payload = dict(values)
        payload.update(provider=provider, account_id=account_id)
        if registry_id is None:
            payload["status"] = "pending_mapping"
        payload["governance_score"] = self.governance_score(payload)
        old = next((r for r in existing if str(r.get("id")) == str(registry_id)), None)
        saved = (
            self.repository.update(context, registry_id, payload)
            if registry_id
            else self.repository.create(context, payload)
        )
        self.repository.append_audit(
            context,
            {
                "registry_id": saved["id"],
                "actor_id": context.user_id,
                "actor_email": context.user_email,
                "action": "update" if registry_id else "create",
                "old_value": old or {},
                "new_value": saved,
                "reason": reason,
            },
        )
        return saved

    def transition(self, context, registry_id: str, status: str, reason: str):
        if not self.permissions(context)["full"]:
            raise PermissionError("cloud account lifecycle denied")
        if status not in {"inactive", "archived"}:
            raise RegistryValidationError("only deactivate or archive is supported")
        return self.save(
            context,
            {
                **next(
                    r for r in self.list_accounts(context) if str(r.get("id")) == str(registry_id)
                ),
                "status": status,
            },
            registry_id=registry_id,
            reason=reason,
        )

    def preview_csv(self, context, content: bytes) -> dict[str, Any]:
        if not self.permissions(context)["edit"]:
            raise PermissionError("cloud account import denied")
        frame = pd.read_csv(BytesIO(content), dtype=str).fillna("")
        missing = [c for c in IMPORT_COLUMNS if c not in frame.columns]
        if missing:
            raise RegistryValidationError("missing columns: " + ", ".join(missing))
        existing = {(r["provider"], r["account_id"]) for r in self.list_accounts(context)}
        identities = [
            (str(r["Provider"]).lower(), str(r["Account ID"])) for _, r in frame.iterrows()
        ]
        duplicate_rows = {
            i
            for i, identity in enumerate(identities)
            if identity in existing or identities.count(identity) > 1
        }
        return {
            "rows": frame.to_dict("records"),
            "valid": len(frame) - len(duplicate_rows),
            "duplicates": sorted(duplicate_rows),
            "can_commit": not duplicate_rows,
        }

    def commit_preview(self, context, preview: Mapping[str, Any], *, reason: str):
        if not preview.get("can_commit"):
            raise RegistryValidationError("import preview contains duplicate rows")
        saved = []
        for row in preview.get("rows") or []:
            saved.append(
                self.save(
                    context,
                    {
                        "provider": row["Provider"],
                        "account_id": row["Account ID"],
                        "account_name": row["Account Name"],
                        "owner": row["Owner"],
                        "business_unit": row["Business Unit"],
                        "department": row["Department"],
                        "application": row["Application"],
                        "environment": row["Environment"],
                        "budget": float(row["Budget"] or 0),
                        "status": "pending_mapping",
                    },
                    reason=reason,
                )
            )
        return saved

    @staticmethod
    def export_csv(rows) -> bytes:
        return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")

    @staticmethod
    def export_excel(rows) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Cloud Accounts")
        return output.getvalue()
