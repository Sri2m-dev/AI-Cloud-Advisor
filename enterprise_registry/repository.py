"""Repository abstractions for WP-006 Phase 1."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Protocol

from data_fabric.foundation import TenantContext
from enterprise_registry.exceptions import (
    BusinessServiceNotFoundError,
    BusinessServiceValidationError,
    BusinessServiceVersionConflictError,
    DuplicateBusinessServiceError,
)
from enterprise_registry.models import BusinessService, normalize_identity

PartitionKey = tuple[str, str]
SourceKey = tuple[str, str]


class BusinessServiceRepository(Protocol):
    """Persistence-neutral, tenant-scoped registry contract."""

    def register(
        self,
        context: TenantContext,
        service: BusinessService,
    ) -> BusinessService: ...

    def get_by_canonical_id(
        self,
        context: TenantContext,
        canonical_id: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService: ...

    def get_by_business_service_id(
        self,
        context: TenantContext,
        business_service_id: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService: ...

    def resolve_alias(
        self,
        context: TenantContext,
        alias: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService: ...

    def list_services(
        self,
        context: TenantContext,
        *,
        business_domain: str | None = None,
        include_inactive: bool = False,
    ) -> list[BusinessService]: ...

    def update(
        self,
        context: TenantContext,
        service: BusinessService,
        *,
        expected_version: int,
    ) -> BusinessService: ...


class InMemoryBusinessServiceRepository(BusinessServiceRepository):
    """Deterministic reference repository; no database or runtime wiring."""

    def __init__(self) -> None:
        self._services: dict[PartitionKey, dict[str, BusinessService]] = {}
        self._service_ids: dict[PartitionKey, dict[str, str]] = {}
        self._sources: dict[PartitionKey, dict[SourceKey, str]] = {}
        self._aliases: dict[PartitionKey, dict[str, str]] = {}

    def register(
        self,
        context: TenantContext,
        service: BusinessService,
    ) -> BusinessService:
        self._assert_scope(context, service)
        partition = self._partition(context)
        services = self._services.setdefault(partition, {})
        service_ids = self._service_ids.setdefault(partition, {})
        sources = self._sources.setdefault(partition, {})
        aliases = self._aliases.setdefault(partition, {})
        normalized_id = normalize_identity(
            service.business_service_id,
            "business_service_id",
        )
        source_key = self._source_key(service)
        if service.canonical_id in services:
            raise DuplicateBusinessServiceError(
                f"canonical_id already registered: {service.canonical_id}"
            )
        if normalized_id in service_ids:
            raise DuplicateBusinessServiceError(
                f"business_service_id already registered: {normalized_id}"
            )
        if source_key in sources:
            raise DuplicateBusinessServiceError(
                "source_system and source_id already identify a business service"
            )
        self._assert_aliases_available(aliases, service.aliases, service.canonical_id)
        stored = self._copy(service)
        services[stored.canonical_id] = stored
        service_ids[normalized_id] = stored.canonical_id
        sources[source_key] = stored.canonical_id
        for alias in stored.aliases:
            aliases[normalize_identity(alias, "alias")] = stored.canonical_id
        return self._copy(stored)

    def get_by_canonical_id(
        self,
        context: TenantContext,
        canonical_id: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService:
        service = self._services.get(self._partition(context), {}).get(canonical_id)
        return self._require_visible(service, canonical_id, include_inactive)

    def get_by_business_service_id(
        self,
        context: TenantContext,
        business_service_id: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService:
        normalized_id = normalize_identity(
            business_service_id,
            "business_service_id",
        )
        canonical_id = self._service_ids.get(self._partition(context), {}).get(
            normalized_id
        )
        if canonical_id is None:
            raise BusinessServiceNotFoundError(
                f"Business service not found: {normalized_id}"
            )
        return self.get_by_canonical_id(
            context,
            canonical_id,
            include_inactive=include_inactive,
        )

    def resolve_alias(
        self,
        context: TenantContext,
        alias: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService:
        normalized_alias = normalize_identity(alias, "alias")
        canonical_id = self._aliases.get(self._partition(context), {}).get(
            normalized_alias
        )
        if canonical_id is None:
            raise BusinessServiceNotFoundError(
                f"Business service alias not found: {normalized_alias}"
            )
        return self.get_by_canonical_id(
            context,
            canonical_id,
            include_inactive=include_inactive,
        )

    def list_services(
        self,
        context: TenantContext,
        *,
        business_domain: str | None = None,
        include_inactive: bool = False,
    ) -> list[BusinessService]:
        domain = str(business_domain or "").strip().casefold()
        services = []
        for service in self._services.get(self._partition(context), {}).values():
            if not include_inactive and not service.active:
                continue
            if domain and service.business_domain.casefold() != domain:
                continue
            services.append(self._copy(service))
        return sorted(services, key=lambda service: service.canonical_id)

    def update(
        self,
        context: TenantContext,
        service: BusinessService,
        *,
        expected_version: int,
    ) -> BusinessService:
        self._assert_scope(context, service)
        partition = self._partition(context)
        current = self._services.get(partition, {}).get(service.canonical_id)
        if current is None:
            raise BusinessServiceNotFoundError(
                f"Business service not found: {service.canonical_id}"
            )
        if current.version != expected_version:
            raise BusinessServiceVersionConflictError(
                f"expected version {expected_version}, found {current.version}"
            )
        if service.version != expected_version + 1:
            raise BusinessServiceVersionConflictError(
                "updated service version must increment by exactly one"
            )
        immutable_identity = (
            current.business_service_id,
            current.canonical_id,
            current.source_system,
            current.source_id,
        )
        updated_identity = (
            service.business_service_id,
            service.canonical_id,
            service.source_system,
            service.source_id,
        )
        if immutable_identity != updated_identity:
            raise BusinessServiceValidationError(
                "business service canonical and source identity are immutable"
            )
        aliases = self._aliases.setdefault(partition, {})
        self._assert_aliases_available(aliases, service.aliases, service.canonical_id)
        for alias, canonical_id in tuple(aliases.items()):
            if canonical_id == service.canonical_id:
                aliases.pop(alias)
        for alias in service.aliases:
            aliases[normalize_identity(alias, "alias")] = service.canonical_id
        stored = self._copy(service)
        self._services[partition][stored.canonical_id] = stored
        return self._copy(stored)

    @staticmethod
    def _assert_scope(context: TenantContext, service: BusinessService) -> None:
        context.assert_record_matches(service, "business_service")

    @staticmethod
    def _partition(context: TenantContext) -> PartitionKey:
        return (context.organization_id, context.tenant_id)

    @staticmethod
    def _source_key(service: BusinessService) -> SourceKey:
        return (
            service.source_system.strip().casefold(),
            service.source_id.strip().casefold(),
        )

    @staticmethod
    def _assert_aliases_available(
        aliases: dict[str, str],
        requested: tuple[str, ...],
        canonical_id: str,
    ) -> None:
        for alias in requested:
            normalized = normalize_identity(alias, "alias")
            existing = aliases.get(normalized)
            if existing is not None and existing != canonical_id:
                raise DuplicateBusinessServiceError(
                    f"alias already registered: {normalized}"
                )

    @staticmethod
    def _require_visible(
        service: BusinessService | None,
        identifier: str,
        include_inactive: bool,
    ) -> BusinessService:
        if service is None or (not include_inactive and not service.active):
            raise BusinessServiceNotFoundError(
                f"Business service not found: {identifier}"
            )
        return InMemoryBusinessServiceRepository._copy(service)

    @staticmethod
    def _copy(service: BusinessService) -> BusinessService:
        return replace(
            service,
            entity=deepcopy(service.entity),
            attributes=dict(service.attributes),
        )
