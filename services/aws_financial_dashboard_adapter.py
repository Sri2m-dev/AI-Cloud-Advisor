"""Generation-pinned repository adapters for DASH-06/07 and the active workspace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from repositories.aws_financial_evidence_repository import FinancialEvidenceUnavailable
from services.aws_financial_import_contribution_verifier import (
    AwsFinancialImportContributionVerifier,
    CanonicalEvidence,
    ProjectionEvidence,
    ProofStatus,
)
from services.aws_financial_ingestion_orchestrator import (
    ImportContributionEvidence,
    ProjectionRefreshEvidence,
)


def _time(value):
    result = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    if result.tzinfo is None:
        raise FinancialEvidenceUnavailable("timezone required")
    return result


def _row(row):
    result = dict(row)
    for key, value in result.items():
        if value is None:
            continue
        if key in {"billing_period_start", "billing_period_end"}:
            result[key] = date.fromisoformat(value) if isinstance(value, str) else value
        elif key.endswith("_at"):
            result[key] = _time(value)
        elif key in {
            "source_cost_total",
            "normalized_cost_total",
            "unblended_cost",
            "total_unblended_spend",
            "variance_amount",
        }:
            if isinstance(value, float):
                raise FinancialEvidenceUnavailable("float financial evidence rejected")
            result[key] = Decimal(value)
    return result


@dataclass(frozen=True)
class AwsDashboardStatus:
    readiness: str = "NOT_READY"
    reason: str = "Verified AWS publication is unavailable; security approvals remain pending."
    posture: EnterpriseFinancialPosture | None = None
    generation_id: str | None = None
    published_at: datetime | None = None


class AwsFinancialDashboardAdapter:
    """One attempt, one scope/query, one captured envelope; never an unbounded shared cache."""

    def __init__(
        self,
        repository,
        *,
        context,
        query,
        prior_import_ids=(),
        request_id,
        expected_previous_generation_id=None,
        tenant_verifier=None,
    ):
        self.repository = repository
        self.context = context
        self.query = query
        self.prior_import_ids = tuple(prior_import_ids)
        self.request_id = request_id
        self.previous = expected_previous_generation_id
        self.tenant_verifier = tenant_verifier
        self.receipt = None
        self._capture = None

    def _scope(self, context):
        if context != self.context:
            raise PermissionError("adapter context mismatch")

    def refresh(self, context, import_id):
        self._scope(context)
        self._capture = None
        self.receipt = self.repository.refresh(
            context,
            (*self.prior_import_ids, import_id),
            self.query,
            trigger_import_id=import_id,
            request_id=self.request_id,
            expected_previous_generation_id=self.previous,
        )
        return ProjectionRefreshEvidence(
            context.organization_id,
            context.tenant_id,
            import_id,
            _time(self.receipt["published_at"]),
        )

    def invalidate(self, organization_id):
        if organization_id == self.context.organization_id:
            self._capture = None

    def read(self, context, import_ids, query):
        self._scope(context)
        if self.tenant_verifier is None or self.tenant_verifier.verify(context) is not True:
            raise PermissionError("authoritative tenant verification required before reading")
        if query != self.query:
            raise FinancialEvidenceUnavailable("query mismatch")
        if self._capture is not None:
            if tuple(self._capture[0]) != tuple(import_ids):
                raise FinancialEvidenceUnavailable("capture membership mismatch")
            return self._capture[1]
        env = self.repository.read(context, import_ids, query)
        if env.get("contract_version") != "nxr-dash-08-v1" or not env.get("snapshot_id"):
            raise FinancialEvidenceUnavailable("snapshot/version missing")
        expected_query = {
            "currency": query.currency,
            "period_start": query.period_start.isoformat(),
            "period_end": query.period_end.isoformat(),
            "spans_multiple_periods": query.spans_multiple_periods,
        }
        if env.get("query") != expected_query or tuple(env["requested_import_ids"]) != tuple(
            import_ids
        ):
            raise FinancialEvidenceUnavailable("wire query or requested membership mismatch")
        pub = env["publication"]
        if not pub or pub.get("is_current") is not True:
            raise FinancialEvidenceUnavailable("current publication missing")
        if self.receipt and any(
            pub.get(k) != self.receipt.get(k)
            for k in ("generation_id", "published_at", "trigger_import_id", "input_digest")
        ):
            raise FinancialEvidenceUnavailable("publication changed after refresh")
        observed, published = _time(env["observed_at"]), _time(pub["published_at"])
        if observed < published:
            raise FinancialEvidenceUnavailable("publication chronology invalid")
        posture_row = pub["posture"]
        required = set(EnterpriseFinancialPosture.__dataclass_fields__)
        if required - posture_row.keys() or any(posture_row[k] is None for k in required):
            raise FinancialEvidenceUnavailable("posture fields missing")
        if posture_row["contract_version"] != "pvt-003c1-v1":
            raise FinancialEvidenceUnavailable("posture version mismatch")
        if any(isinstance(v, float) for v in posture_row.values()) or isinstance(
            pub["total"], float
        ):
            raise FinancialEvidenceUnavailable("float financial posture rejected")
        posture = EnterpriseFinancialPosture.from_mapping(posture_row)
        if posture.generated_at != published or posture.organization_id != context.organization_id:
            raise FinancialEvidenceUnavailable("posture identity/publication mismatch")
        canonical = env["canonical"]
        if env.get("missing_import_ids") or env.get("unexpected_import_ids") or env.get("reasons"):
            raise FinancialEvidenceUnavailable("complete envelope contains failure diagnostics")
        authorization = env.get("authorization", {})
        if (
            authorization.get("actor_auth_uid") != context.user_id
            or authorization.get("permission") != "read"
        ):
            raise FinancialEvidenceUnavailable("authorized subject mismatch")
        canonical_facts = {f["cloud_cost_fact_id"]: _row(f) for f in canonical["facts"]}
        published_facts = pub.get("published_facts")
        if not isinstance(published_facts, list) or len(published_facts) != len(canonical_facts):
            raise FinancialEvidenceUnavailable("published fact snapshots incomplete")
        published_ids = set()
        for frozen in published_facts:
            row = _row(frozen)
            fid = row["cloud_cost_fact_id"]
            if (
                fid in published_ids
                or row.pop("generation_id", None) != pub["generation_id"]
                or row.pop("included_in_resolved", None) is not True
            ):
                raise FinancialEvidenceUnavailable("published fact identity mismatch")
            published_ids.add(fid)
            if row != canonical_facts.get(fid):
                raise FinancialEvidenceUnavailable(
                    "published fact snapshot differs from canonical evidence"
                )
        sources = {}
        for source in env["sources"]:
            row = _row(source)
            if row.get("attestation_status") != "verified" or row["import_id"] in sources:
                raise FinancialEvidenceUnavailable("attestation missing/revoked/duplicate")
            sources[row["import_id"]] = row
        revision = pub["generation_id"]
        bundle = ImportContributionEvidence(
            sources,
            CanonicalEvidence(
                context.organization_id,
                context.tenant_id,
                query,
                revision,
                observed,
                True,
                tuple(map(_row, canonical["imports"])),
                tuple(map(_row, canonical["facts"])),
                tuple(map(_row, canonical["reconciliations"])),
            ),
            ProjectionEvidence(
                context.organization_id,
                context.tenant_id,
                query,
                revision,
                observed,
                published,
                True,
                tuple(map(_row, pub["published_imports"])),
                tuple(pub["included_fact_ids"]),
                Decimal(pub["total"]),
                posture,
            ),
        )
        proof = AwsFinancialImportContributionVerifier(
            tenant_verifier=self.tenant_verifier,
            source_reader=bundle,
            canonical_reader=bundle,
            projection_reader=bundle,
        ).verify(context, import_ids, query)
        if proof.status is not ProofStatus.PASS:
            raise FinancialEvidenceUnavailable(f"contribution verification failed: {proof.reasons}")
        self._capture = (tuple(import_ids), bundle, env)
        return bundle

    def get_financial_posture(self, context, *, currency):
        self._scope(context)
        if currency != self.query.currency or self.receipt is None:
            raise FinancialEvidenceUnavailable("matching refresh receipt required")
        bundle = self.read(context, tuple(self.receipt["import_ids"]), self.query)
        return bundle.projection.posture

    def status(self, context, import_ids):
        try:
            self.invalidate(context.organization_id)
            bundle = self.read(context, tuple(import_ids), self.query)
            pub = self._capture[2]["publication"]
            return AwsDashboardStatus(
                "READY",
                "Verified canonical AWS publication.",
                bundle.projection.posture,
                pub["generation_id"],
                _time(pub["published_at"]),
            )
        except PermissionError:
            return AwsDashboardStatus(
                reason="Approved AWS read authority or membership is unavailable."
            )
        except Exception:
            return AwsDashboardStatus(
                reason="Canonical AWS evidence is incomplete, stale, or unavailable."
            )


def dashboard_status(context, adapter=None, import_ids=()):
    # No issuer, provider, attester or client is obtained from browser session values.
    if adapter is None:
        return AwsDashboardStatus()
    return adapter.status(context, import_ids)
