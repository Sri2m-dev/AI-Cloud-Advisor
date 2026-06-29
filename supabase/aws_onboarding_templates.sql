create table if not exists public.aws_onboarding_templates (
    id uuid primary key default gen_random_uuid(),
    template_name text not null,
    template_type text not null,
    template_version text not null default '1.0',
    payload jsonb not null,
    description text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_aws_onboarding_templates_unique
    on public.aws_onboarding_templates (template_name, template_type, template_version);

insert into public.aws_onboarding_templates (
    template_name,
    template_type,
    template_version,
    payload,
    description
)
values
    (
        'Nexora AWS IAM Permissions Policy',
        'IAM_POLICY',
        '1.0',
        '{
          "Version": "2012-10-17",
          "Statement": [
            {
              "Sid": "NexoraCostAccess",
              "Effect": "Allow",
              "Action": [
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
                "ce:GetDimensionValues",
                "ce:GetReservationUtilization",
                "ce:GetSavingsPlansUtilization"
              ],
              "Resource": "*"
            },
            {
              "Sid": "NexoraDiscoveryAccess",
              "Effect": "Allow",
              "Action": [
                "sts:GetCallerIdentity",
                "ec2:DescribeInstances",
                "ec2:DescribeVpcs",
                "ec2:DescribeVolumes",
                "ec2:DescribeSnapshots",
                "ec2:DescribeSecurityGroups",
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation",
                "rds:DescribeDBInstances",
                "lambda:ListFunctions",
                "eks:ListClusters",
                "eks:DescribeCluster",
                "compute-optimizer:GetEC2InstanceRecommendations",
                "compute-optimizer:GetEBSVolumeRecommendations",
                "trustedadvisor:DescribeChecks",
                "trustedadvisor:DescribeCheckResult"
              ],
              "Resource": "*"
            }
          ]
        }'::jsonb,
        'Read-only IAM permissions required for Nexora AWS cost, resource, and recommendation ingestion.'
    ),
    (
        'Nexora AWS Trust Policy',
        'TRUST_POLICY',
        '1.0',
        '{
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "AWS": "<NEXORA_AWS_ACCOUNT_ARN>"
              },
              "Action": "sts:AssumeRole",
              "Condition": {
                "StringEquals": {
                  "sts:ExternalId": "<CUSTOMER_EXTERNAL_ID>"
                }
              }
            }
          ]
        }'::jsonb,
        'Cross-account trust policy template with external ID support.'
    )
on conflict do nothing;

