# P4.3.1 Current Enterprise Entity Model

Status: discovery complete before P4.3.1 runtime implementation
Baseline: `a6c47bcfe6a3342d821bd9584b7807b7cec9e6e0`
Release parent: `07525c351b8722a3b27b866f5f8b03cafdc27ecd`

## Discovery conclusion

Nexora already has the required canonical foundations. The authoritative identity/index
contract is `data_fabric.contracts.EnterpriseEntity`; relationships use
`EnterpriseRelationship`; deterministic matching and `NO_MATCH`/duplicate decisions use
`data_fabric.identity`; entity/relationship registration, lineage, provenance,
versioning, quality, ownership, ontology, and taxonomy are established P3 contracts.
P4.2 adds field-level classification evidence and protected approvals.

The active landscape also contains domain models and legacy persistence projections.
Those remain sources of truth for their domain attributes. P4.3.1 must adapt them into
the P3 canonical identity/index contract and must not introduce a generic entity table,
new graph, new identity resolver, or copied financial facts.

## Current-state inventory

| Entity type | Current source of truth | Existing ID | Canonical ID available | Tenant key | Versioning | Ownership | Classification | Graph | Financial attribution | Duplicate/overlap risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Organization | authenticated tenant, `core.entities.organization` | organization ID | P3 entity supports it; legacy core ID varies | organization + tenant | P3 entity/version contracts | tenant administration | ontology/P4.2 compatible | P3 relationship registry | financial organization scope | Medium: auth, core, and database representations |
| Business unit | `core.entities.business_unit`, business architecture services | domain ID/name | P3 canonical entity possible | organization/tenant or legacy organization | P3 when adapted | owner fields vary | P4.2 account field | business graph and P3 graph | allocation dimension | High: name-based legacy rows |
| Department | `core.entities.department`, registry/account mappings | domain ID/name | P3 `DEPARTMENT` exists | organization/tenant or organization | P3 when adapted | owner varies | P4.2 account field | P3 graph compatible | allocation dimension | High: duplicated text in mappings |
| Portfolio | technology/application portfolio services | portfolio name/ID | No consistent active canonical mapping | organization | domain-specific | varies | ontology compatible | portfolio/technology views | indirect | High |
| Capability | `core.entities.business_capability`, capability service | entity/domain ID | P3 `BUSINESS_CAPABILITY` exists | organization/tenant | P3 when adapted | supported | ontology compatible | business graph | indirect | Medium |
| Business service | `enterprise_registry.BusinessService`, business-service services | business_service_id | Yes, deterministic tenant-bound ID | organization + tenant | explicit optimistic version | required in released registry contract | ontology/P4.2 account field | EMRP + business-service graph | cost service/allocation | Low in new registry; medium with legacy services |
| Business process | `core.entities.business_process`/service | domain ID | P3 `BUSINESS_PROCESS` exists | organization/tenant | P3 when adapted | supported by domain | ontology compatible | business graph | indirect | Medium |
| Application | `core.entities.application`, application inventory/services | application ID/name | P3 `APPLICATION` exists; not universal in legacy rows | organization/tenant or company | mixed | owner/domain fields | P4.2 account field | application, technology, knowledge graphs | application attribution | High across inventory/registry/graph projections |
| Product/platform | application/technology domain metadata | domain ID/name | No dedicated released type | organization | domain-specific | varies | ontology compatible | graph metadata | indirect | High semantic overlap with application/technology |
| Technology | `core.entities.technology`, technology inventory | technology ID/name | P3 `TECHNOLOGY` exists | organization/tenant or company | mixed | owner varies | ontology compatible | technology graph/digital twin | technology spend | High across inventory, graph, and twin |
| Cloud account/subscription/project | FG-001 `cloud_account_registry` | provider + account ID | Registry ID exists; P3 canonical mapping not universal | organization + tenant | FG-002 version/audit | governed mapping fields | full P4.2 field classification | financial/account relationships | canonical CUR account dimension | Medium: cloud accounts and legacy connector rows |
| Cloud resource | connector discovery and `core.entities.cloud_resource` | provider resource ID/ARN | P3 `CLOUD_RESOURCE` exists | organization/tenant | connector/P3 lineage | tags/registry mapping | evidence source | relationship graph/digital twin | CUR resource attribution | High across discovered assets and graph copies |
| Database/storage/network/Kubernetes/AI platform | connector-discovered resource metadata | provider resource ID | represented generically as cloud resource today | organization/tenant | connector/P3 lineage | tags | evidence source | technology graph/twin | CUR resource attribution | Medium semantic subtype ambiguity |
| SaaS product/application | SaaS governance tables and `core.entities.saas_application` | tool/application ID/name | P3 `SAAS_APPLICATION` exists | company or organization/tenant | domain-specific | owner/user assignment | limited; ontology compatible | knowledge/technology graph | SaaS cost table | High between tool/product/application terms |
| Vendor | `core.entities.vendor`, SaaS/contracts metadata | vendor ID/name | P3 `VENDOR` exists | organization/tenant or company | P3 when adapted | relationship-based | ontology compatible | supplier relationships | contract/SaaS cost | Medium name/alias duplication |
| Contract/license | SaaS governance contracts/licenses | table ID/vendor reference | P3 `CONTRACT`; license lacks dedicated type | company/organization | domain timestamps | assignee/owner varies | none | supplier/association graph possible | contract/license cost | Medium legacy company scope |
| User/owner/team | auth users, `core.entities.user/team`, P3 ownership | user/email/domain ID | owner P3 type exists; user/team not consistently canonical | organization/tenant | auth/domain-specific | self-referential | owner field classifications | ownership relationships | allocation responsibility | High across auth and ownership strings |
| Cost center | `core.entities.cost_center`, account mappings | cost-center code | P3 `COST_CENTER` exists | organization/tenant | P3 when adapted | business ownership | P4.2 account field | funding relationships | primary allocation dimension | Medium text duplication |
| Spend source/budget/allocation target | Enterprise Financial Data Fabric | import/account/dimension IDs | canonical financial references, not general entities | organization/tenant | immutable facts + derived versions | finance governance | classification drives eligibility | account/entity references | authoritative | High if copied into registry; copying prohibited |
| Risk/recommendation/approval/policy/evidence | governance services and P3 contracts | domain IDs | P3 types exist | organization/tenant | explicit audit/version semantics | assigned authority | evidence/classification links | governance relationships | optimization context | Low when referenced, high if duplicated |
| Connector-discovered entity | connector registry/discovered assets | source system + source ID | identity candidate supported | organization/tenant | sync/lineage history | tag-derived | classification evidence source | relationship graph | possible CUR correlation | High until identity resolution completes |
| Digital-twin entity | technology/business twin models | twin/node ID | references domain entities inconsistently | organization/tenant | snapshots/state | inherited | derived signals | twin graph | cost signals | Medium; twin must remain a projection |

## Contract and overlap findings

1. Two Python `EnterpriseEntity` concepts exist: the P3 contract under `data_fabric` and
   a legacy/core model under `core.entities`. P3 is authoritative for P4.3.
2. `enterprise_registry` already composes P3 contracts for Business Services and EMRP;
   it is the correct package to extend with thin adapters and a tenant-scoped facade.
3. `supabase/universal_entity_registry.sql` describes legacy public projections, while
   P3 persistence migrations own canonical Data Fabric entity/relationship records.
   No new persistence is justified for P4.3.1.
4. Relationship graphs, technology graphs, knowledge graphs, and twins are domain
   projections. P3 `RelationshipRegistry` remains the canonical relationship contract.
5. Financial facts remain authoritative in the Enterprise Financial Data Fabric and are
   exposed only by references/adapters.
6. Approved P4.2 classifications must be read as protected facts; later inference is
   evidence, never an overwrite.

## Migration decision

Existing P3 contracts are sufficient for an identity/index layer. P4.3.1 therefore
requires no schema migration. Additive Python contract fields and taxonomy values can be
introduced with defaults, while adapters preserve domain primary keys and source data.
