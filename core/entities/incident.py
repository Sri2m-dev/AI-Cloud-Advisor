from dataclasses import dataclass, field

from core.entities.entity import EnterpriseEntity, EntityType


@dataclass(slots=True)
class Incident(EnterpriseEntity):
    entity_type: str = field(init=False, default=EntityType.INCIDENT.value)

