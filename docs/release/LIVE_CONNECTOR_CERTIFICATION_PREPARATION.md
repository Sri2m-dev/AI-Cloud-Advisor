# Live Connector Certification Preparation

**Status:** AWS_LIVE_CERTIFICATION_READY (conditional)
**Status:** AZURE_LIVE_CERTIFICATION_READY (conditional)

This preparation was read-only. No AWS, Azure, Supabase, client, commit, or push
was performed. No credentials were requested or printed.

## AWS contract

### Authentication

Use an IAM role assumed through STS with temporary credentials:

- `role_arn`: required role ARN
- `external_id`: recommended and required when the trust policy enforces it
- `region`: one connector region, defaulting to `us-east-1`

The current connector validates caller identity with STS and reuses the assumed
session. Access-key fallback must not be used for client certification unless
explicitly approved.

### Code-proven API permissions

The current connector directly calls:

- `sts:GetCallerIdentity`
- `ce:GetCostAndUsage`
- `ec2:DescribeInstances`
- `ec2:DescribeVpcs`
- `s3:ListAllMyBuckets`
- `rds:DescribeDBInstances`
- `lambda:ListFunctions`
- `eks:ListClusters`
- `compute-optimizer:GetEC2InstanceRecommendations`

`organizations:ListAccounts` appears in validation references but is not proven
as a required executed discovery call; confirm before adding it.

A placeholder-only policy should grant only these actions on the dedicated
non-production account/role. Do not use `AdministratorAccess`.

### Required local configuration

- `AWS_REGION`
- role ARN and external ID through the connector's runtime configuration/secret
  provider
- no secret values in repository files or reports

### Scope and certification sequence

1. Assume the dedicated non-production role.
2. Validate STS caller identity and account binding.
3. Run the connector permission validator.
4. Stop on any denied required permission.
5. Run bounded account discovery.
6. Run a one-day Cost Explorer query.
7. Run bounded EC2, S3, RDS, Lambda, VPC, and EKS discovery.
8. Produce SourceInstance/SourceFact evidence and checkpoint state.
9. Replay the same checkpoint and verify idempotency/freshness.
10. Verify no automatic unsupported canonicalization and no destructive calls.

### AWS readiness

**AWS_LIVE_CERTIFICATION_READY** once the dedicated non-production role,
external ID/trust relationship, Cost Explorer availability, and network access
are confirmed by the operator.

## Azure contract

### Authentication

Preferred method: Microsoft Entra service principal using
`ClientSecretCredential` or the already-supported workload identity path.

Required scope:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET` through the secret provider
- `AZURE_SUBSCRIPTION_ID`

The connector requests the Azure management token scope
`https://management.azure.com/.default`.

### Code-proven API permissions

The current connector directly calls:

- Microsoft Entra token acquisition
- `Microsoft.Resources/subscriptions/resourceGroups/read`
- `Microsoft.Resources/subscriptions/resources/read`
- `Microsoft.CostManagement/query/action`

A subscription-level `Reader` role covers the resource read operations. Cost
Management query permission must be granted separately through the narrowest
supported built-in/custom role available in the target subscription. Do not
use `Owner` or `Contributor` unless the provider confirms the current code
requires an operation beyond the listed reads.

### Scope and certification sequence

1. Acquire an Entra token and validate tenant/subscription binding.
2. Run the connector connection test.
3. Discover the dedicated subscription record.
4. Discover resource groups and mapped resources.
5. Run a one-day Cost Management query.
6. Produce SourceInstance/SourceFact evidence and checkpoint state.
7. Replay the checkpoint and verify freshness/idempotency behavior.
8. Verify unknown resource types remain excluded/explicitly unavailable.
9. Verify no writes, deletes, or automatic canonicalization occur.

### Azure readiness

**AZURE_LIVE_CERTIFICATION_READY** once the dedicated non-production service
principal, subscription role assignment, Cost Management permission, provider
registration, and network access are confirmed by the operator.

## Safety boundaries

- No external calls were made.
- No client credentials are present in this contract.
- AWS and Azure operations are read-only discovery/cost queries.
- Connector observations remain SourceFacts until governed canonicalization.
- Tenant binding must be explicit; no default organization is permitted.
- Live credentials must be configured locally only and never sent through chat.

## Test-count note

The current RC-001 release evidence records `1873 passed, 2 skipped, 0
failures`. A later local gate invocation reported `1639 passed, 2 skipped`; the
repository does not currently contain a preserved log explaining that narrower
count. Treat `1639` as a command-scope discrepancy requiring command/log capture,
not as a product regression. The full release baseline remains the recorded
`1873` suite until a reproducible command explains the difference.

## Live execution decision

Both connectors are conditionally ready for a dedicated non-production live
certification. Execution remains deferred until dedicated AWS/Azure access is
explicitly authorized and configured locally. No credentials or external
systems were touched in this preparation gate.
