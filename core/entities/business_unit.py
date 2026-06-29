from dataclasses import dataclass, field

from core.entities.entity import EnterpriseEntity, EntityType


@dataclass(slots=True)
class BusinessUnit(EnterpriseEntity):
    entity_type: str = field(init=False, default=EntityType.BUSINESS_UNIT.value)

