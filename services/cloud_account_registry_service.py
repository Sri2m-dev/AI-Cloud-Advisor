"""Governed cloud-account registry domain service."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping

import pandas as pd

from auth.authenticated_tenant import AuthenticatedTenantContext
from repositories.cloud_account_registry_repository import CloudAccountRegistryRepository

PROVIDERS = {"aws", "azure", "gcp"}
READ_ROLES = {"super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"}
EDIT_ROLES = {"super_admin", "client_admin", "finance", "operations"}
FULL_ROLES = {"super_admin", "client_admin", "operations"}
IMPORT_COLUMNS = ["Provider", "Account ID", "Account Name", "Owner", "Business Unit", "Department", "Application", "Environment", "Budget"]


class RegistryValidationError(ValueError):
    pass


class CloudAccountRegistryService:
    def __init__(self, repository: CloudAccountRegistryRepository) -> None:
        self.repository = repository

    @staticmethod
    def permissions(context: AuthenticatedTenantContext) -> dict[str, bool]:
        return {"read": context.role in READ_ROLES, "edit": context.role in EDIT_ROLES, "full": context.role in FULL_ROLES}

    @staticmethod
    def governance_score(row: Mapping[str, Any]) -> int:
        ownership = sum(bool(row.get(k)) for k in ("owner", "technical_owner", "finance_owner")) / 3
        mapping = sum(bool(row.get(k)) for k in ("business_unit", "department", "application", "business_service", "cost_center")) / 5
        tags = max(0.0, min(1.0, float(row.get("tags_coverage") or 0) / 100))
        allocation = 1.0 if row.get("cost_center") and float(row.get("monthly_budget") or row.get("budget") or 0) >= 0 else 0.0
        synced = row.get("last_synchronization")
        freshness = 1.0 if synced else 0.0
        return round(ownership * 30 + mapping * 25 + tags * 15 + allocation * 15 + freshness * 15)

    @staticmethod
    def governance_label(score: int) -> str:
        if score >= 95: return "Excellent"
        if score >= 85: return "Good"
        if score >= 70: return "Needs Improvement"
        return "Critical"

    def list_accounts(self, context: AuthenticatedTenantContext):
        if not self.permissions(context)["read"]: raise PermissionError("cloud account registry read denied")
        return self.repository.list_accounts(context)

    def dashboard(self, context: AuthenticatedTenantContext) -> dict[str, Any]:
        rows = self.list_accounts(context)
        scores = [int(r.get("governance_score") or self.governance_score(r)) for r in rows]
        return {"accounts": rows, "total": len(rows), "aws": sum(r.get("provider") == "aws" for r in rows), "azure": sum(r.get("provider") == "azure" for r in rows), "gcp": sum(r.get("provider") == "gcp" for r in rows), "active": sum(r.get("status") == "active" for r in rows), "pending": sum(r.get("status") in {"pending", "pending_mapping"} for r in rows), "unknown": sum(r.get("status") == "unknown" for r in rows), "average_governance": round(sum(scores) / len(scores), 1) if scores else 0.0}

    def save(self, context: AuthenticatedTenantContext, values: Mapping[str, Any], *, registry_id: str | None = None, reason: str):
        if not self.permissions(context)["edit"]: raise PermissionError("cloud account registry edit denied")
        provider = str(values.get("provider") or "").strip().lower()
        account_id = str(values.get("account_id") or "").strip()
        if provider not in PROVIDERS: raise RegistryValidationError("provider must be AWS, Azure, or GCP")
        if not account_id: raise RegistryValidationError("account_id is required")
        if not str(reason or "").strip(): raise RegistryValidationError("modification reason is required")
        existing = self.repository.list_accounts(context)
        if any(r.get("provider") == provider and r.get("account_id") == account_id and str(r.get("id")) != str(registry_id or "") for r in existing):
            raise RegistryValidationError(f"duplicate {provider} account identity")
        payload = dict(values); payload.update(provider=provider, account_id=account_id)
        payload["governance_score"] = self.governance_score(payload)
        old = next((r for r in existing if str(r.get("id")) == str(registry_id)), None)
        saved = self.repository.update(context, registry_id, payload) if registry_id else self.repository.create(context, payload)
        self.repository.append_audit(context, {"registry_id": saved["id"], "actor_id": context.user_id, "actor_email": context.user_email, "action": "update" if registry_id else "create", "old_value": old or {}, "new_value": saved, "reason": reason})
        return saved

    def transition(self, context, registry_id: str, status: str, reason: str):
        if not self.permissions(context)["full"]: raise PermissionError("cloud account lifecycle denied")
        if status not in {"inactive", "archived"}: raise RegistryValidationError("only deactivate or archive is supported")
        return self.save(context, {**next(r for r in self.list_accounts(context) if str(r["id"]) == str(registry_id)), "status": status}, registry_id=registry_id, reason=reason)

    def preview_csv(self, context, content: bytes) -> dict[str, Any]:
        if not self.permissions(context)["edit"]: raise PermissionError("cloud account import denied")
        frame = pd.read_csv(BytesIO(content), dtype=str).fillna("")
        missing = [c for c in IMPORT_COLUMNS if c not in frame.columns]
        if missing: raise RegistryValidationError("missing columns: " + ", ".join(missing))
        existing = {(r["provider"], r["account_id"]) for r in self.list_accounts(context)}
        identities = [(str(r["Provider"]).lower(), str(r["Account ID"])) for _, r in frame.iterrows()]
        duplicate_rows = {i for i, identity in enumerate(identities) if identity in existing or identities.count(identity) > 1}
        return {"rows": frame.to_dict("records"), "valid": len(frame) - len(duplicate_rows), "duplicates": sorted(duplicate_rows), "can_commit": not duplicate_rows}

    def commit_preview(self, context, preview: Mapping[str, Any], *, reason: str):
        if not preview.get("can_commit"):
            raise RegistryValidationError("import preview contains duplicate rows")
        saved = []
        for row in preview.get("rows") or []:
            saved.append(self.save(context, {
                "provider": row["Provider"], "account_id": row["Account ID"],
                "account_name": row["Account Name"], "owner": row["Owner"],
                "business_unit": row["Business Unit"], "department": row["Department"],
                "application": row["Application"], "environment": row["Environment"],
                "budget": float(row["Budget"] or 0), "status": "pending_mapping",
            }, reason=reason))
        return saved

    @staticmethod
    def export_csv(rows) -> bytes:
        return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")

    @staticmethod
    def export_excel(rows) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer: pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Cloud Accounts")
        return output.getvalue()
