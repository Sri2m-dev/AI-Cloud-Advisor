from dataclasses import dataclass, field

from core.entities.entity import EnterpriseEntity, EntityType


@dataclass(slots=True)
class CloudResource(EnterpriseEntity):
    entity_type: str = field(init=False, default=EntityType.CLOUD_RESOURCE.value)

