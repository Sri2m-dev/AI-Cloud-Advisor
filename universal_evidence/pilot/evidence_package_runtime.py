from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

from data_fabric.foundation import TenantContext
from data_fabric.identity import InMemoryIdentityResolver
from data_fabric.registry import (
    InMemoryEntityRegistry,
    InMemoryRelationshipRegistry,
)
from data_fabric.source_facts import (
    SourceFactService,
    SourceInstance,
    SQLiteSourceFactRepository,
)
from enterprise_registry.canonical_service import EnterpriseRegistryService
from universal_evidence.pilot.evidence_package_composition import (
    CertifiedPackageComposition,
    compose_certified_package_source,
)
from universal_evidence.pilot.reconciliation import (
    GovernedIdentityReconciliationService,
)


@dataclass(frozen=True)
class CertifiedPackageSource:
    source_type: str
    file_id: str
    rows: tuple[Mapping[str, Any], ...]
    mapping_decision_ids: tuple[str, ...] = ()
    normalization_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackageSourcePublication:
    source_type: str
    source_instance_id: str
    input_fact_count: int
    published_fact_count: int
    unchanged_fact_count: int
    composition: CertifiedPackageComposition


@dataclass(frozen=True)
class CertifiedPackageRuntimeResult:
    publications: tuple[PackageSourcePublication, ...]
    reconciliation: Any
    source_fact_service: SourceFactService
    registry: EnterpriseRegistryService


@dataclass(frozen=True)
class CertifiedPackageAnalysis:
    package_id: str
    admissions: tuple[Any, ...]
    sources: tuple[CertifiedPackageSource, ...]
    normalization_runs: tuple[Any, ...]
    runtime: CertifiedPackageRuntimeResult
    coverage: Any
    intelligence: Any
    owner_id: str


def analyze_certified_package(
    *,
    package,
    prospect_tenant,
    authenticated,
    source_fact_root,
    semantic_service=None,
    normalization_service=None,
):
    """Compose existing package authorities under one authenticated analysis."""
    from hashlib import sha256

    from auth.authenticated_tenant import AuthenticatedTenantContext
    from universal_evidence.activation import (
        ActivationScope,
        ActivationStage,
        RoutingReason,
        ScopeLevel,
    )
    from universal_evidence.pilot.admission import admit_uploaded_evidence, admitted_source_rows
    from universal_evidence.pilot.evidence_package_coverage import assess_package_governed_coverage
    from universal_evidence.pilot.evidence_package_governance import govern_certified_package_source
    from universal_evidence.pilot.evidence_package_intelligence import (
        assess_certified_evidence_package,
    )
    from universal_evidence.pilot.runtime import (
        get_normalization_pilot_service,
        get_semantic_pilot_service,
    )
    from universal_evidence.production_workflow import activate_production_workflow
    from universal_evidence.security import WorkflowAuthorizationContext

    if not isinstance(authenticated, AuthenticatedTenantContext):
        raise PermissionError("Authenticated package tenant context is required")
    if {s.source_type for s in package.manifest.files} != {
        "org",
        "inventory",
        "cost",
        "application_mapping",
    }:
        raise ValueError("Certified package requires all four source types")
    semantic_service = semantic_service or get_semantic_pilot_service()
    normalization_service = normalization_service or get_normalization_pilot_service()
    # Physical separation also protects prospects within the same tenant and
    # packages reusing a customer-selected package identifier.
    identity = sha256(
        repr(
            (
                authenticated.organization_id,
                authenticated.tenant_id,
                prospect_tenant.tenant_id,
                package.manifest,
            )
        ).encode()
    ).hexdigest()
    analysis_id = "evidence-package-" + identity
    authorization = WorkflowAuthorizationContext.from_authenticated(
        authenticated,
        prospect_id=prospect_tenant.tenant_id,
        analysis_id=analysis_id,
    )
    actor = authorization.governance_actor()
    admissions, sources, runs = [], [], []
    for entry in package.manifest.files:
        admission = admit_uploaded_evidence(
            prospect_tenant,
            filename=entry.filename,
            content=package.content(entry.source_type),
            tenant_context=authenticated,
            analysis_id=analysis_id,
        )
        authorization.authorize_scope(admission.scope)
        activate_production_workflow(admission)
        activation = semantic_service.activation_resolver.resolve(
            ActivationScope(
                ScopeLevel.ANALYSIS,
                organization_id=authenticated.organization_id,
                tenant_id=authenticated.tenant_id,
                prospect_id=prospect_tenant.tenant_id,
                analysis_id=analysis_id,
            )
        )
        if (
            activation.stage < ActivationStage.CAPABILITY_VISIBLE
            or RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes
        ):
            raise PermissionError("Certified package workflow is blocked by activation policy")
        governed = govern_certified_package_source(
            admission=admission,
            source_type=entry.source_type,
            semantic_service=semantic_service,
            actor=actor,
        )
        source_runs = normalization_service.execute(admission, actor=actor)
        if not governed.decisions or not source_runs:
            raise PermissionError("Certified package source has no governed normalization")
        sheets = admitted_source_rows(admission)
        if len(sheets) != 1 or not sheets[0]:
            raise ValueError("Certified package sources require one table with a header")
        headers, *values = sheets[0]
        if len(set(headers)) != len(headers):
            raise ValueError("Certified package source contains duplicate headers")
        rows = tuple(
            dict(zip(headers, row)) for row in values if any(v not in (None, "") for v in row)
        )
        sources.append(
            CertifiedPackageSource(
                entry.source_type,
                admission.file_id,
                rows,
                tuple(d.decision_id for d in governed.decisions),
                tuple(r.normalization_run_id for r in source_runs),
            )
        )
        admissions.append(admission)
        runs.extend(source_runs)
    intelligence = assess_certified_evidence_package(
        sources,
        package_period=package.manifest.raw.get("period"),
    )
    coverage = assess_package_governed_coverage(
        normalization_service=normalization_service, runs=runs
    )
    database = Path(source_fact_root) / identity / "source_facts.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    runtime = execute_certified_package_runtime(
        package_id=package.package_id,
        sources=sources,
        organization_id=authenticated.organization_id,
        tenant_id=authenticated.tenant_id,
        prospect_id=prospect_tenant.tenant_id,
        analysis_id=analysis_id,
        source_fact_database=database,
        activation=activation,
    )
    return CertifiedPackageAnalysis(
        package.package_id,
        tuple(admissions),
        tuple(sources),
        tuple(runs),
        runtime,
        coverage,
        intelligence,
        authenticated.user_id,
    )


def _source_instance(
    *,
    organization_id: str,
    tenant_id: str,
    package_id: str,
    source_type: str,
    file_id: str,
) -> SourceInstance:
    return SourceInstance(
        source_instance_id=(f"evidence-package:{package_id}:{source_type}"),
        organization_id=organization_id,
        tenant_id=tenant_id,
        source_type=source_type,
        source_system="certified_evidence_package",
        connector_type="evidence_package",
        connector_version="1.0",
        configuration_reference=(f"evidence-package:{package_id}:{file_id}"),
        credential_reference=None,
    )


def _schema_for(composition: CertifiedPackageComposition) -> dict[str, str]:
    return {fact.predicate: "evidence" for fact in composition.source_facts}


def execute_certified_package_runtime(
    *,
    package_id: str,
    sources: Iterable[CertifiedPackageSource],
    organization_id: str,
    tenant_id: str,
    prospect_id: str,
    analysis_id: str,
    source_fact_database: str | Path,
    registry: EnterpriseRegistryService | None = None,
    activation: Any | None = None,
    execution_id: str = "initial",
) -> CertifiedPackageRuntimeResult:
    context = TenantContext(
        organization_id,
        tenant_id,
    )

    repository = SQLiteSourceFactRepository(source_fact_database)
    fact_service = SourceFactService(
        context,
        repository,
    )

    if registry is None:
        registry = EnterpriseRegistryService(
            context,
            role="operations",
            entities=InMemoryEntityRegistry(),
            identities=InMemoryIdentityResolver(),
            relationships=InMemoryRelationshipRegistry(),
        )

    reconciler = GovernedIdentityReconciliationService(registry)

    if activation is None:
        activation = SimpleNamespace(
            stage=2,
            reason_codes=(),
        )

    publications = []
    observations = []

    for source in sources:
        composition = compose_certified_package_source(
            source_type=source.source_type,
            rows=source.rows,
            file_id=source.file_id,
            organization_id=organization_id,
            tenant_id=tenant_id,
            prospect_id=prospect_id,
            analysis_id=analysis_id,
            source_id=(f"{package_id}:{source.source_type}"),
            mapping_decision_ids=(source.mapping_decision_ids),
            normalization_references=(source.normalization_references),
        )

        instance = _source_instance(
            organization_id=organization_id,
            tenant_id=tenant_id,
            package_id=package_id,
            source_type=source.source_type,
            file_id=source.file_id,
        )

        fact_service.register(instance)

        publication = fact_service.publish(
            instance,
            composition.source_facts,
            run_id=(f"{package_id}:{execution_id}:" f"{source.source_type}:{source.file_id}"),
            checkpoint_after=source.file_id,
            schema=_schema_for(composition),
        )

        publications.append(
            PackageSourcePublication(
                source_type=source.source_type,
                source_instance_id=(instance.source_instance_id),
                input_fact_count=len(composition.source_facts),
                published_fact_count=len(publication.facts),
                unchanged_fact_count=(publication.unchanged),
                composition=composition,
            )
        )

        observations.extend(composition.identity_observations)

    reconciliation = reconciler.reconcile(
        tuple(observations),
        context=context,
        activation=activation,
    )

    return CertifiedPackageRuntimeResult(
        publications=tuple(publications),
        reconciliation=reconciliation,
        source_fact_service=fact_service,
        registry=registry,
    )
