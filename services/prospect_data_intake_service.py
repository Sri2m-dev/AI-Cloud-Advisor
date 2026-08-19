from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from cryptography.fernet import Fernet, InvalidToken

PROSPECT_CLASSIFICATION = "PROSPECT_DEMONSTRATION_DATA"
PROSPECT_WATERMARK = "Prospect Demonstration · Temporary Analysis · Not Certified Production Data"
DEFAULT_RETENTION_DAYS = 30
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
ALLOWED_ROLES = frozenset({"sales_engineer", "finance"})
SUPPORTED_PROFILES = (
    "AWS billing/CUR-derived CSV",
    "Azure cost export",
    "GCP billing export",
    "SaaS/license CSV or Excel",
    "Generic technology-cost Excel/CSV",
    "Manual invoice/bill spreadsheet",
)
STORE_ROOT = Path(os.getenv("NEXORA_PROSPECT_DATA_ROOT", "var/prospect_data"))


class ProspectIntakeError(RuntimeError):
    """Raised when prospect data cannot safely enter the temporary analysis boundary."""


@dataclass(frozen=True)
class ProspectTenant:
    tenant_id: str
    audit_id: str
    created_at: str
    expires_at: str
    retention_days: int
    classification: str = PROSPECT_CLASSIFICATION


@dataclass(frozen=True)
class ProspectAnalysis:
    tenant_id: str
    audit_id: str
    analysis_timestamp: str
    expires_at: str
    total_spend: float
    currency: str
    cloud_spend: float
    saas_spend: float
    other_spend: float
    unclassified_spend: float
    evidence_coverage: float
    confidence: float
    opportunity_identified: float
    opportunity_evidence_qualified: float
    opportunity_recommended: float
    opportunity_approved: float
    opportunity_realized: float
    row_count: int
    watermark: str = PROSPECT_WATERMARK


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fernet(key: str | bytes | None = None) -> Fernet:
    material = key or os.getenv("NEXORA_PROSPECT_DATA_KEY", "")
    if isinstance(material, str):
        material = material.encode("ascii")
    if not material:
        raise ProspectIntakeError("NEXORA_PROSPECT_DATA_KEY is required for encrypted storage")
    try:
        return Fernet(material)
    except (ValueError, TypeError) as exc:
        raise ProspectIntakeError("NEXORA_PROSPECT_DATA_KEY is not a valid Fernet key") from exc


def generate_encryption_key() -> str:
    """Generate a key for administrator-managed secret storage; never persist it here."""
    return Fernet.generate_key().decode("ascii")


def prospect_encryption_key() -> str:
    """Resolve the configured master key, with a local-only development fallback."""
    configured = os.getenv("NEXORA_PROSPECT_DATA_KEY", "").strip()
    if configured:
        return configured
    environment = os.getenv("ENVIRONMENT", os.getenv("CLOUD_ADVISOR_ENV", "development"))
    if environment.strip().lower() == "production":
        raise ProspectIntakeError(
            "NEXORA_PROSPECT_DATA_KEY must be supplied through production secret management"
        )
    path = Path(".streamlit/prospect-data.key")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(generate_encryption_key(), encoding="ascii")
    return path.read_text(encoding="ascii").strip()


def _require_role(role: str) -> None:
    if str(role or "").strip().lower() not in ALLOWED_ROLES:
        raise ProspectIntakeError("prospect intake requires Sales Engineer or Finance Operator")


def _tenant_dir(tenant_id: str, root: Path = STORE_ROOT) -> Path:
    if not str(tenant_id).startswith("prospect-") or any(
        token in str(tenant_id) for token in ("..", "/", "\\")
    ):
        raise ProspectIntakeError("invalid prospect tenant identifier")
    return root.resolve() / tenant_id


def _write_encrypted(path: Path, payload: bytes, cipher: Fernet) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cipher.encrypt(payload))


def _read_encrypted(path: Path, cipher: Fernet) -> bytes:
    try:
        return cipher.decrypt(path.read_bytes())
    except (InvalidToken, OSError) as exc:
        raise ProspectIntakeError("encrypted prospect artifact cannot be read") from exc


def _tenant_cipher(
    tenant_id: str, *, root: Path, key: str | bytes | None = None
) -> Fernet:
    master = _fernet(key)
    try:
        tenant_key = master.decrypt((_tenant_dir(tenant_id, root) / "key.enc").read_bytes())
        return Fernet(tenant_key)
    except (InvalidToken, OSError, ValueError) as exc:
        raise ProspectIntakeError("prospect tenant encryption key cannot be read") from exc


def _audit(
    tenant: ProspectTenant,
    event: str,
    actor: str,
    details: dict[str, Any],
    *,
    root: Path,
    cipher: Fernet,
) -> None:
    path = _tenant_dir(tenant.tenant_id, root) / "audit.enc"
    events: list[dict[str, Any]] = []
    if path.exists():
        events = json.loads(_read_encrypted(path, cipher).decode("utf-8"))
    previous_hash = events[-1]["event_hash"] if events else "GENESIS"
    record = {
        "audit_id": tenant.audit_id,
        "tenant_id": tenant.tenant_id,
        "timestamp": _utc_now().isoformat(),
        "event": event,
        "actor": actor,
        "details": details,
        "previous_hash": previous_hash,
    }
    record["event_hash"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    events.append(record)
    _write_encrypted(path, json.dumps(events, sort_keys=True).encode("utf-8"), cipher)


def create_prospect_tenant(
    prospect_name: str,
    *,
    consent: bool,
    actor: str,
    role: str,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    root: Path = STORE_ROOT,
    key: str | bytes | None = None,
) -> ProspectTenant:
    _require_role(role)
    if not consent:
        raise ProspectIntakeError("explicit prospect consent is required")
    if not str(prospect_name or "").strip():
        raise ProspectIntakeError("prospect name is required")
    if retention_days < 1 or retention_days > 90:
        raise ProspectIntakeError("retention must be between 1 and 90 days")
    master_cipher = _fernet(key)
    now = _utc_now()
    tenant = ProspectTenant(
        tenant_id=f"prospect-{uuid4()}",
        audit_id=f"audit-{uuid4()}",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(days=retention_days)).isoformat(),
        retention_days=retention_days,
    )
    tenant_path = _tenant_dir(tenant.tenant_id, root)
    tenant_path.mkdir(parents=True, exist_ok=False)
    tenant_key = Fernet.generate_key()
    cipher = Fernet(tenant_key)
    (tenant_path / "key.enc").write_bytes(master_cipher.encrypt(tenant_key))
    manifest = {**asdict(tenant), "prospect_name": prospect_name.strip()}
    _write_encrypted(
        tenant_path / "manifest.enc", json.dumps(manifest).encode("utf-8"), cipher
    )
    _audit(
        tenant,
        "PROSPECT_TENANT_CREATED",
        actor,
        {"consent": True, "retention_days": retention_days},
        root=root,
        cipher=cipher,
    )
    return tenant


def scan_upload(filename: str, content: bytes) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ProspectIntakeError("only CSV and XLSX inputs are permitted")
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ProspectIntakeError("upload is empty or exceeds the 25 MB limit")
    lowered = content.lower()
    if b"eicar-standard-antivirus-test-file" in lowered:
        raise ProspectIntakeError("malware signature detected")
    if content.startswith((b"MZ", b"\x7fELF")):
        raise ProspectIntakeError("executable content is not permitted")
    if suffix == ".xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                total = sum(item.file_size for item in archive.infolist())
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise ProspectIntakeError("spreadsheet expands beyond the safety limit")
                names = {item.filename.lower() for item in archive.infolist()}
                if any("vbaproject" in name or name.endswith(".bin") for name in names):
                    raise ProspectIntakeError("active or embedded spreadsheet content is forbidden")
        except zipfile.BadZipFile as exc:
            raise ProspectIntakeError("invalid XLSX container") from exc
    return {
        "scanner": "builtin_signature_and_container_scan_v1",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "status": "PASS",
    }


ALIASES = {
    "provider": ("provider", "cloud", "vendor", "publisher"),
    "service": ("service", "service_name", "product", "metercategory", "sku"),
    "cost": (
        "cost",
        "amount",
        "total_cost",
        "unblendedcost",
        "costinbillingcurrency",
        "billedcost",
    ),
    "currency": ("currency", "billingcurrency", "currencycode"),
    "business_unit": ("business_unit", "department", "cost_center"),
    "application": ("application", "app", "product_name"),
    "potential_savings": ("potential_savings", "estimated_savings", "savings_opportunity"),
    "license_quantity": ("license_quantity", "licenses", "seats", "quantity"),
    "used_quantity": ("used_quantity", "used_licenses", "active_seats", "used"),
}


def _read_frame(filename: str, content: bytes) -> pd.DataFrame:
    try:
        if Path(filename).suffix.lower() == ".csv":
            return pd.read_csv(io.BytesIO(content))
        return pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ProspectIntakeError("file could not be parsed as a supported tabular input") from exc


def _column_map(frame: pd.DataFrame) -> dict[str, str]:
    normalized = {
        str(column).strip().lower().replace(" ", "").replace("_", ""): str(column)
        for column in frame.columns
    }
    mapping: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            key = alias.replace("_", "")
            if key in normalized:
                mapping[canonical] = normalized[key]
                break
    if "cost" not in mapping:
        raise ProspectIntakeError("a supported cost or amount column is required")
    return mapping


def normalize_upload(profile: str, filename: str, content: bytes) -> pd.DataFrame:
    if profile not in SUPPORTED_PROFILES:
        raise ProspectIntakeError("unsupported prospect input profile")
    frame = _read_frame(filename, content)
    if frame.empty or len(frame) > 500_000:
        raise ProspectIntakeError("input must contain between 1 and 500,000 rows")
    mapping = _column_map(frame)
    canonical = pd.DataFrame(index=frame.index)
    for field in ALIASES:
        canonical[field] = frame[mapping[field]] if field in mapping else None
    canonical["cost"] = pd.to_numeric(canonical["cost"], errors="coerce")
    if canonical["cost"].isna().all() or (canonical["cost"].dropna() < 0).any():
        raise ProspectIntakeError("cost values must contain non-negative numeric evidence")
    canonical["cost"] = canonical["cost"].fillna(0.0)
    canonical["potential_savings"] = pd.to_numeric(
        canonical["potential_savings"], errors="coerce"
    )
    canonical["currency"] = canonical["currency"].fillna("UNKNOWN").astype(str)
    canonical["provider"] = canonical["provider"].fillna("UNKNOWN").astype(str)
    canonical["service"] = canonical["service"].fillna("UNKNOWN").astype(str)
    canonical["source_profile"] = profile
    return canonical


def _analyze(tenant: ProspectTenant, frame: pd.DataFrame) -> ProspectAnalysis:
    total = float(frame["cost"].sum())
    provider_text = frame["provider"].str.lower()
    profile_text = frame["source_profile"].str.lower()
    cloud_mask = provider_text.str.contains("aws|azure|gcp|google|cloud", regex=True) | (
        profile_text.str.contains("aws|azure|gcp", regex=True)
    )
    saas_mask = profile_text.str.contains("saas|license", regex=True)
    classified = (frame["provider"] != "UNKNOWN") | (frame["service"] != "UNKNOWN")
    unclassified = float(frame.loc[~classified, "cost"].sum())
    evidence_coverage = round(float(classified.mean() * 100), 1)
    explicit = float(frame["potential_savings"].dropna().clip(lower=0).sum())
    license_qty = pd.to_numeric(frame["license_quantity"], errors="coerce")
    used_qty = pd.to_numeric(frame["used_quantity"], errors="coerce")
    unused_ratio = (
        (license_qty - used_qty).clip(lower=0) / license_qty.replace(0, pd.NA)
    ).fillna(0)
    license_opportunity = float((frame.loc[saas_mask, "cost"] * unused_ratio[saas_mask]).sum())
    identified = min(total, explicit + license_opportunity)
    qualified = identified if evidence_coverage >= 70 else 0.0
    confidence = round(min(95.0, evidence_coverage * 0.9), 1)
    return ProspectAnalysis(
        tenant_id=tenant.tenant_id,
        audit_id=tenant.audit_id,
        analysis_timestamp=_utc_now().isoformat(),
        expires_at=tenant.expires_at,
        total_spend=total,
        currency=next((value for value in frame["currency"] if value != "UNKNOWN"), "UNKNOWN"),
        cloud_spend=float(frame.loc[cloud_mask, "cost"].sum()),
        saas_spend=float(frame.loc[saas_mask, "cost"].sum()),
        other_spend=float(frame.loc[~(cloud_mask | saas_mask), "cost"].sum()),
        unclassified_spend=unclassified,
        evidence_coverage=evidence_coverage,
        confidence=confidence,
        opportunity_identified=identified,
        opportunity_evidence_qualified=qualified,
        opportunity_recommended=0.0,
        opportunity_approved=0.0,
        opportunity_realized=0.0,
        row_count=len(frame),
    )


def ingest_upload(
    tenant: ProspectTenant,
    *,
    profile: str,
    filename: str,
    content: bytes,
    actor: str,
    role: str,
    root: Path = STORE_ROOT,
    key: str | bytes | None = None,
) -> ProspectAnalysis:
    _require_role(role)
    cipher = _tenant_cipher(tenant.tenant_id, root=root, key=key)
    scan = scan_upload(filename, content)
    frame = normalize_upload(profile, filename, content)
    tenant_path = _tenant_dir(tenant.tenant_id, root)
    if not tenant_path.exists():
        raise ProspectIntakeError("prospect tenant does not exist")
    _write_encrypted(tenant_path / "source.enc", content, cipher)
    _write_encrypted(
        tenant_path / "normalized.enc",
        frame.to_json(orient="records").encode("utf-8"),
        cipher,
    )
    analysis = _analyze(tenant, frame)
    _write_encrypted(
        tenant_path / "analysis.enc",
        json.dumps(asdict(analysis), sort_keys=True).encode("utf-8"),
        cipher,
    )
    _audit(
        tenant,
        "PROSPECT_DATA_INGESTED",
        actor,
        {
            "profile": profile,
            "source_sha256": scan["sha256"],
            "scanner": scan["scanner"],
            "row_count": len(frame),
        },
        root=root,
        cipher=cipher,
    )
    return analysis


def load_analysis(
    tenant_id: str, *, root: Path = STORE_ROOT, key: str | bytes | None = None
) -> ProspectAnalysis:
    cipher = _tenant_cipher(tenant_id, root=root, key=key)
    payload = json.loads(
        _read_encrypted(_tenant_dir(tenant_id, root) / "analysis.enc", cipher).decode("utf-8")
    )
    return ProspectAnalysis(**payload)


def record_activity(
    tenant: ProspectTenant,
    *,
    event: str,
    actor: str,
    role: str,
    details: dict[str, Any] | None = None,
    root: Path = STORE_ROOT,
    key: str | bytes | None = None,
) -> None:
    """Record a non-sensitive activity in the encrypted, hash-chained tenant audit trail."""
    _require_role(role)
    _audit(
        tenant,
        event,
        actor,
        details or {},
        root=root,
        cipher=_tenant_cipher(tenant.tenant_id, root=root, key=key),
    )


def purge_tenant(
    tenant: ProspectTenant,
    *,
    actor: str,
    role: str,
    root: Path = STORE_ROOT,
    key: str | bytes | None = None,
    force: bool = False,
) -> None:
    _require_role(role)
    if not force and _utc_now() < datetime.fromisoformat(tenant.expires_at):
        raise ProspectIntakeError("prospect tenant has not reached its expiration date")
    cipher = _tenant_cipher(tenant.tenant_id, root=root, key=key)
    tenant_path = _tenant_dir(tenant.tenant_id, root)
    _audit(
        tenant,
        "PROSPECT_TENANT_PURGE_STARTED",
        actor,
        {"secure_scope": "sources, normalized data, reports, conversations, caches, exports"},
        root=root,
        cipher=cipher,
    )
    if tenant_path.exists():
        shutil.rmtree(tenant_path)
    tombstones = root.resolve() / "purge_tombstones.jsonl"
    tombstones.parent.mkdir(parents=True, exist_ok=True)
    tombstone = {
        "tenant_id": tenant.tenant_id,
        "audit_id": tenant.audit_id,
        "event": "PROSPECT_TENANT_PURGED",
        "timestamp": _utc_now().isoformat(),
    }
    with tombstones.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(tombstone, sort_keys=True) + "\n")


def purge_expired(
    *,
    actor: str,
    role: str,
    root: Path = STORE_ROOT,
    key: str | bytes | None = None,
) -> list[str]:
    _require_role(role)
    purged: list[str] = []
    if not root.exists():
        return purged
    for path in root.iterdir():
        if not path.is_dir() or not path.name.startswith("prospect-"):
            continue
        cipher = _tenant_cipher(path.name, root=root, key=key)
        manifest = json.loads(_read_encrypted(path / "manifest.enc", cipher).decode("utf-8"))
        tenant = ProspectTenant(
            **{field: manifest[field] for field in ProspectTenant.__dataclass_fields__}
        )
        if _utc_now() >= datetime.fromisoformat(tenant.expires_at):
            purge_tenant(tenant, actor=actor, role=role, root=root, key=key)
            purged.append(tenant.tenant_id)
    return purged
