from dataclasses import dataclass, field

from core.entities.entity import EnterpriseEntity, EntityType


@dataclass(slots=True)
class Technology(EnterpriseEntity):
    entity_type: str = field(init=False, default=EntityType.TECHNOLOGY.value)

