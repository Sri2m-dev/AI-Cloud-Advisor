# PUE-000 Semantic Taxonomy

## Identifier policy

PUE concept identifiers are lowercase hierarchical paths such as `financial.cost.total` and carry
an explicit integer version. Definitions, expected primitive types, optional allowed units, and
cardinality expectations are versioned with the concept. Aliases are discovery inputs and never
canonical identifiers. Customer-specific vocabulary must not enter the shared concept definition.

This is an architectural catalog, not a classifier or a claim that any uploaded field has a meaning.
Before implementation, candidates intended for canonical promotion must be reconciled with
`data_fabric.semantic` ontology types and governance.

## Initial dimensions and concept families

| Dimension | Concept families and examples |
| --- | --- |
| Financial | `financial.cost.*`, `financial.price`, `financial.savings`, `financial.budget`, `financial.commitment`, `financial.currency` |
| Cloud | `cloud.provider`, `cloud.account`, `cloud.subscription`, `cloud.project`, `cloud.region`, `cloud.availability_zone` |
| Technology | `technology.service`, `technology.product`, `technology.platform`, `technology.database`, `technology.middleware`, `technology.operating_system` |
| Resource | `resource.identifier`, `resource.name`, `resource.type`, `resource.instance`, `resource.cluster`, `resource.storage`, `resource.network` |
| Organization | `organization.business_unit`, `organization.department`, `organization.cost_center`, `organization.legal_entity` |
| Ownership | `ownership.owner`, `ownership.team`, `ownership.manager`, `ownership.support_group` |
| Application | `application.name`, `application.workload`, `application.system`, `application.product` |
| Business | `business.service`, `business.capability`, `business.product` |
| SaaS | `saas.vendor`, `saas.license`, `saas.seat`, `saas.utilization`, `saas.subscription` |
| Contract | `contract.identifier`, `contract.start_date`, `contract.end_date`, `contract.renewal_date`, `contract.commitment` |
| Operational | `operational.cpu`, `operational.memory`, `operational.uptime`, `operational.utilization`, `operational.incident_count`, `operational.availability` |
| Security | `security.vulnerability`, `security.severity`, `security.compliance`, `security.control_status` |
| Geography | `geography.country`, `geography.location`, `geography.region` |
| Tagging | `tagging.environment`, `tagging.project`, `tagging.owner`, `tagging.custom` |

## Governance rules

- Similar labels across dimensions remain distinct candidates until governed.
- A concept does not encode a provider inference; `technology.service` does not imply AWS.
- Currency and unit concepts govern measure comparability.
- Concept deprecation creates a new version or successor relationship; it does not rewrite history.
- Alias learning must remain tenant/prospect scoped unless anonymized and explicitly approved.
- Confidence thresholds are policy configuration, not taxonomy properties.
