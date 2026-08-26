"""Bounded, explainable PUE-008 analytical language aliases."""

MEASURE_ALIASES = {
    "cost": "financial.cost",
    "spend": "financial.cost",
    "expense": "financial.cost",
}

DIMENSION_ALIASES = {
    "service": "technology.service",
    "technology service": "technology.service",
    "provider": "cloud.provider",
    "cloud provider": "cloud.provider",
    "region": "geography.region",
    "application": "application.name",
    "owner": "ownership.owner",
    "renewal": "contract.renewal_date",
    "renewal date": "contract.renewal_date",
    "enabled": "tagging.enabled",
}

VALUE_ALIASES = {
    "ec2": ("technology.service", "EC2"),
    "rds": ("technology.service", "RDS"),
    "aws": ("cloud.provider", "AWS"),
    "azure": ("cloud.provider", "Azure"),
    "gcp": ("cloud.provider", "GCP"),
}

BOOLEAN_LITERALS = {
    "true": True,
    "false": False,
    "enabled": True,
    "disabled": False,
}
