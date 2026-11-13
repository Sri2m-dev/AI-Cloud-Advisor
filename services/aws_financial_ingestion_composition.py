"""Explicit backend composition; no infrastructure or privileged authorities are created."""

from dataclasses import dataclass
from threading import RLock
from uuid import UUID

from auth.authenticated_tenant import AuthenticatedTenantContext
from repositories.aws_cur_ingestion_repository import SupabaseAwsCurIngestionRepository
from repositories.aws_financial_evidence_repository import AwsFinancialEvidenceRepository
from services.aws_financial_dashboard_adapter import (
    AwsDashboardStatus,
    AwsFinancialDashboardAdapter,
)
from services.aws_financial_import_contribution_verifier import (
    AwsFinancialImportContributionVerifier,
    DashboardQuery,
)
from services.aws_financial_ingestion_orchestrator import AwsFinancialIngestionOrchestrator
from services.demo_tenant_service import DEMO_ORGANIZATION_ID


def compose_aws_financial_ingestion(
    *,
    backend_client,
    context,
    query,
    request_id,
    tenant_verifier,
    independent_reconciler,
    grant_provider=None,
    prior_import_ids=(),
    expected_previous_generation_id=None,
):
    """Authorities must be supplied by separately approved backend composition.

    A missing issuer fails closed at the repository. Passing a service-role client
    does not authorize a human, issue grants, attest bytes or activate database privileges.
    """
    persistence = SupabaseAwsCurIngestionRepository(backend_client)
    repository = AwsFinancialEvidenceRepository(backend_client, grant_provider=grant_provider)
    adapter = AwsFinancialDashboardAdapter(
        repository,
        context=context,
        query=query,
        prior_import_ids=prior_import_ids,
        request_id=request_id,
        expected_previous_generation_id=expected_previous_generation_id,
        tenant_verifier=tenant_verifier,
    )
    orchestrator = AwsFinancialIngestionOrchestrator(
        tenant_verifier=tenant_verifier,
        account_ownership=persistence,
        persistence=persistence,
        reconciler=independent_reconciler,
        projection_refresher=adapter,
        dashboard=adapter,
        contribution_verifier=AwsFinancialImportContributionVerifier,
        evidence_provider=adapter,
    )
    return orchestrator, adapter


# Backend process configuration only. Never populated from Streamlit session/query values.
# Installing dependencies is not approval; SQL authority denial and privileges remain intact.


@dataclass(frozen=True)
class AwsFinancialReadSelection:
    organization_id: str
    tenant_id: str
    actor_auth_uid: str
    import_ids: tuple[str, ...]
    query: DashboardQuery


@dataclass(frozen=True)
class AwsFinancialReadBackend:
    client: object
    tenant_verifier: object
    selection_reader: object
    existing_read_grant_lookup: object


_read_backend = None
_read_backend_lock = RLock()


def configure_aws_financial_read_backend(backend: AwsFinancialReadBackend | None) -> None:
    """Server bootstrap injection only; does not issue authorities or activate SQL.

    The default is disabled. After approvals, the operator supplies a backend verifier,
    canonical coverage reader and lookup of an already issued request-bound read grant.
    No function in this module mints a capability or reads browser configuration.
    """
    if backend is not None and not isinstance(backend, AwsFinancialReadBackend):
        raise TypeError("backend-owned AwsFinancialReadBackend required")
    global _read_backend
    with _read_backend_lock:
        _read_backend = backend


class _ReadOnlyFinancialClient:
    def __init__(self, client):
        self.client = client

    def rpc(self, name, params):
        if name != "read_aws_financial_contribution_evidence_v1":
            raise PermissionError("page composition permits financial reads only")
        return self.client.rpc(name, params)


def aws_financial_dashboard_status(context):
    """Resolve a fresh backend-owned canonical read for the active Executive panel."""
    with _read_backend_lock:
        backend = _read_backend
    if backend is None:
        return AwsDashboardStatus()
    try:
        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("authenticated context required")
        UUID(context.user_id)
        if context.organization_id == DEMO_ORGANIZATION_ID:
            raise PermissionError("demo cannot certify AWS publication")
        if backend.tenant_verifier.verify(context) is not True:
            raise PermissionError("authoritative membership verification failed")
        # Backend canonical coverage, not client import IDs or a caller tenant override.
        selection = backend.selection_reader(context)
        if not isinstance(selection, AwsFinancialReadSelection):
            raise ValueError("canonical coverage unavailable")
        if (selection.organization_id, selection.tenant_id, selection.actor_auth_uid) != (
            context.organization_id,
            context.tenant_id,
            context.user_id,
        ):
            raise PermissionError("backend selection crosses identity boundary")
        if not isinstance(selection.query, DashboardQuery) or not selection.import_ids:
            raise ValueError("explicit canonical query and coverage required")

        def existing_grant(operation):
            if operation.permission != "read" or operation.context != context:
                raise PermissionError("read capability lookup scope mismatch")
            return backend.existing_read_grant_lookup(operation)

        repository = AwsFinancialEvidenceRepository(
            _ReadOnlyFinancialClient(backend.client), grant_provider=existing_grant
        )
        # No refresh request ID or receipt is invented for a dashboard read.
        adapter = AwsFinancialDashboardAdapter(
            repository,
            context=context,
            query=selection.query,
            request_id=None,
            tenant_verifier=backend.tenant_verifier,
        )
        return adapter.status(context, selection.import_ids)
    except PermissionError:
        return AwsDashboardStatus(
            reason="Approved AWS read authority or membership is unavailable."
        )
    except Exception:
        return AwsDashboardStatus(reason="Canonical AWS coverage or evidence is unavailable.")
