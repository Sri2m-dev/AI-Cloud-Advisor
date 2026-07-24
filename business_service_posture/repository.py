"""Persistence-neutral version repository for Business Service posture."""

from __future__ import annotations

from typing import Protocol

from business_service_posture.models import BusinessServicePosture
from data_fabric.foundation import TenantContext


class BusinessServicePostureRepository(Protocol):
    def publish(
        self,
        context: TenantContext,
        posture: BusinessServicePosture,
    ) -> BusinessServicePosture: ...

    def latest(
        self,
        context: TenantContext,
        business_service_id: str,
    ) -> BusinessServicePosture | None: ...

    def history(
        self,
        context: TenantContext,
        business_service_id: str,
    ) -> list[BusinessServicePosture]: ...

    def get_version(
        self,
        context: TenantContext,
        business_service_id: str,
        posture_version: int,
    ) -> BusinessServicePosture | None: ...


class InMemoryBusinessServicePostureRepository:
    """Test/reference store; no database or runtime adoption."""

    def __init__(self) -> None:
        self._versions: dict[
            tuple[str, str, str],
            list[BusinessServicePosture],
        ] = {}

    def publish(
        self,
        context: TenantContext,
        posture: BusinessServicePosture,
    ) -> BusinessServicePosture:
        context.assert_record_matches(posture, "business service posture")
        key = self._key(context, posture.business_service_id)
        versions = self._versions.setdefault(key, [])
        expected_version = len(versions) + 1
        if posture.posture_version != expected_version:
            raise ValueError(
                f"posture version must be {expected_version}, "
                f"received {posture.posture_version}"
            )
        versions.append(posture)
        return posture

    def latest(
        self,
        context: TenantContext,
        business_service_id: str,
    ) -> BusinessServicePosture | None:
        versions = self._versions.get(self._key(context, business_service_id), [])
        return versions[-1] if versions else None

    def history(
        self,
        context: TenantContext,
        business_service_id: str,
    ) -> list[BusinessServicePosture]:
        return list(
            self._versions.get(
                self._key(context, business_service_id),
                [],
            )
        )

    def get_version(
        self,
        context: TenantContext,
        business_service_id: str,
        posture_version: int,
    ) -> BusinessServicePosture | None:
        if posture_version < 1:
            return None
        versions = self._versions.get(
            self._key(context, business_service_id),
            [],
        )
        return next(
            (
                item
                for item in versions
                if item.posture_version == posture_version
            ),
            None,
        )

    @staticmethod
    def _key(
        context: TenantContext,
        business_service_id: str,
    ) -> tuple[str, str, str]:
        return (
            context.organization_id,
            context.tenant_id,
            business_service_id,
        )
