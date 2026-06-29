from dataclasses import dataclass, field

from core.entities.entity import EnterpriseEntity, EntityType


@dataclass(slots=True)
class BusinessCapability(EnterpriseEntity):
    entity_type: str = field(init=False, default=EntityType.BUSINESS_CAPABILITY.value)

