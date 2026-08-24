# P4.3.1 Canonical Enterprise Registry

## Architecture decision

P4.3.1 composes the released P3 Data Fabric contracts and the P4.2
classification engine. It does not add a generic entity table, graph, identity
resolver, lineage system, classification system, or financial ledger.

`data_fabric.contracts.EnterpriseEntity` remains the canonical identity/index
contract. Additive optional fields expose canonical/display names, lifecycle and
classification states, governed references, and validity bounds without changing
existing source primary keys. Deterministic UUID5 canonical IDs bind entity type,
tenant, source system, and normalized source identity.

## Runtime flow

1. Runtime composition selects the existing Supabase configuration in a valid
   configured environment and SQLite in local development.
2. Production with absent, placeholder, or invalid Supabase configuration fails
   closed.
3. Thin domain adapters index Cloud Accounts, Applications, Business Services,
   Technology, and SaaS entities. Domain repositories remain authoritative.
4. The P3 identity resolver handles aliases, duplicates, and `NO_MATCH`; source
   primary keys are never rewritten.
5. P3 relationship, lineage, provenance, quality, ownership, and version contracts
   remain authoritative.
6. P4.2 classifications are exposed by reference. Approved values are protected
   from later inference.
7. Financial context is queried from the Financial Data Fabric and returned by
   reference. Spend and CUR facts are never copied into the registry.

## Taxonomy

The additive taxonomy covers business, application, technology, SaaS/vendor,
people/ownership, and financial-reference entities. It preserves every released P3
type and relationship value.

## Security model

All service operations require an authenticated `TenantContext`. Records are
asserted against both organization and tenant. Read access is limited to
`super_admin`, `client_admin`, `executive`, `cio`, `finance`, `operations`, and
`auditor`; mutation is limited to `super_admin`, `client_admin`, and `operations`.
The page is read-only and does not bypass authentication or RBAC.

## User experience

The Enterprise Registry page provides tenant-scoped search/filter, ten posture
metrics, and Overview, Ownership, Relationships, Financial Context, Health, Risk,
Lineage, Provenance, and Versions tabs. Empty optional domain sources are handled
without a traceback.

## Persistence and migration

No schema migration is required. This is an identity/index composition over released
domain stores and P3 contracts.
