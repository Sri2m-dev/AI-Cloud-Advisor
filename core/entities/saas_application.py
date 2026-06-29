from dataclasses import dataclass, field

from core.entities.entity import EnterpriseEntity, EntityType


@dataclass(slots=True)
class SaaSApplication(EnterpriseEntity):
    entity_type: str = field(init=False, default=EntityType.SAAS_APPLICATION.value)

