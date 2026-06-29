from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.entities.entity import RelationshipDirection, RelationshipStrength


class RelationshipGroup(str, Enum):
    OWNERSHIP = "Ownership"
    DEPENDENCY = "Dependency"
    COST = "Cost"
    GOVERNANCE = "Governance"
    RISK = "Risk"
    OPERATIONS = "Operations"
    SECURITY = "Security"
    AI = "AI"


class OntologyRelationshipType(str, Enum):
    OWNS = "OWNS"
    MANAGES = "MANAGES"
    BELONGS_TO = "BELONGS_TO"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    RUNS_ON = "RUNS_ON"
    CONNECTS_TO = "CONNECTS_TO"
    DEPLOYED_IN = "DEPLOYED_IN"
    SUPPLIES = "SUPPLIES"
    INCURS_COST = "INCURS_COST"
    ALLOCATED_TO = "ALLOCATED_TO"
    FUNDED_BY = "FUNDED_BY"
    FUNDS = "FUNDS"
    GOVERNED_BY = "GOVERNED_BY"
    APPROVED_BY = "APPROVED_BY"
    CONTROLLED_BY = "CONTROLLED_BY"
    HAS_RISK = "HAS_RISK"
    MITIGATED_BY = "MITIGATED_BY"
    MITIGATES = "MITIGATES"
    IMPACTS = "IMPACTS"
    MONITORED_BY = "MONITORED_BY"
    INCIDENT_FOR = "INCIDENT_FOR"
    ALERT_FOR = "ALERT_FOR"
    PROTECTED_BY = "PROTECTED_BY"
    HAS_CONTROL = "HAS_CONTROL"
    VIOLATES_POLICY = "VIOLATES_POLICY"
    RECOMMENDED_BY = "RECOMMENDED_BY"
    EXPLAINED_BY = "EXPLAINED_BY"
    AUTOMATED_BY = "AUTOMATED_BY"
    REDUCES_COST = "REDUCES_COST"


@dataclass(frozen=True, slots=True)
class RelationshipDefinition:
    name: str
    group: RelationshipGroup
    description: str
    inverse_name: str | None = None
    direction: str = RelationshipDirection.FORWARD.value
    default_strength: str = RelationshipStrength.MEDIUM.value
    ontology_version: str = "1.2.1"
    is_canonical: bool = True


CANONICAL_RELATIONSHIP_DEFINITIONS: dict[str, RelationshipDefinition] = {
    item.name: item
    for item in [
        RelationshipDefinition("OWNS", RelationshipGroup.OWNERSHIP, "Entity has accountability for another entity."),
        RelationshipDefinition("MANAGES", RelationshipGroup.OWNERSHIP, "Entity operationally manages another entity."),
        RelationshipDefinition("BELONGS_TO", RelationshipGroup.OWNERSHIP, "Entity belongs to an owning organization or group."),
        RelationshipDefinition("USES", RelationshipGroup.DEPENDENCY, "Entity consumes or uses another entity."),
        RelationshipDefinition("DEPENDS_ON", RelationshipGroup.DEPENDENCY, "Entity requires another entity to function."),
        RelationshipDefinition("RUNS_ON", RelationshipGroup.DEPENDENCY, "Application or workload runs on technology."),
        RelationshipDefinition("CONNECTS_TO", RelationshipGroup.DEPENDENCY, "Entity connects to another entity."),
        RelationshipDefinition("DEPLOYED_IN", RelationshipGroup.DEPENDENCY, "Technology or resource is deployed in an environment or account."),
        RelationshipDefinition("SUPPLIES", RelationshipGroup.DEPENDENCY, "Vendor supplies a technology or service."),
        RelationshipDefinition("INCURS_COST", RelationshipGroup.COST, "Entity incurs measurable cost."),
        RelationshipDefinition("ALLOCATED_TO", RelationshipGroup.COST, "Cost or resource allocation is assigned to an entity."),
        RelationshipDefinition("FUNDED_BY", RelationshipGroup.COST, "Entity is funded by another entity."),
        RelationshipDefinition("FUNDS", RelationshipGroup.COST, "Cost center or funding source funds another entity."),
        RelationshipDefinition("GOVERNED_BY", RelationshipGroup.GOVERNANCE, "Entity is governed by a policy or authority."),
        RelationshipDefinition("APPROVED_BY", RelationshipGroup.GOVERNANCE, "Entity or action is approved by another entity."),
        RelationshipDefinition("CONTROLLED_BY", RelationshipGroup.GOVERNANCE, "Entity is controlled by a governance mechanism."),
        RelationshipDefinition("HAS_RISK", RelationshipGroup.RISK, "Entity has an associated risk."),
        RelationshipDefinition("MITIGATED_BY", RelationshipGroup.RISK, "Risk or entity is mitigated by another entity."),
        RelationshipDefinition("MITIGATES", RelationshipGroup.RISK, "Control or recommendation mitigates a risk."),
        RelationshipDefinition("IMPACTS", RelationshipGroup.RISK, "Risk, incident, or dependency impacts an entity."),
        RelationshipDefinition("MONITORED_BY", RelationshipGroup.OPERATIONS, "Entity is monitored by an operational tool."),
        RelationshipDefinition("INCIDENT_FOR", RelationshipGroup.OPERATIONS, "Incident is associated with an impacted entity."),
        RelationshipDefinition("ALERT_FOR", RelationshipGroup.OPERATIONS, "Alert is associated with an impacted entity."),
        RelationshipDefinition("PROTECTED_BY", RelationshipGroup.SECURITY, "Entity is protected by a security control or tool."),
        RelationshipDefinition("HAS_CONTROL", RelationshipGroup.SECURITY, "Entity has an attached control."),
        RelationshipDefinition("VIOLATES_POLICY", RelationshipGroup.SECURITY, "Entity violates a policy."),
        RelationshipDefinition("RECOMMENDED_BY", RelationshipGroup.AI, "Entity or action is recommended by an AI system."),
        RelationshipDefinition("EXPLAINED_BY", RelationshipGroup.AI, "Entity or decision is explained by an AI system."),
        RelationshipDefinition("AUTOMATED_BY", RelationshipGroup.AI, "Entity or action is automated by an AI system."),
        RelationshipDefinition("REDUCES_COST", RelationshipGroup.AI, "Recommendation reduces cost for an entity."),
    ]
}


def relationship_names() -> set[str]:
    return set(CANONICAL_RELATIONSHIP_DEFINITIONS)
