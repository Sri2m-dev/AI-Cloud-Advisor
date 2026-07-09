"""Shared enums for canonical enterprise model contracts."""

from enum import Enum


class EntityType(str, Enum):
    """Provider-neutral canonical enterprise entity types."""

    BUSINESS_CAPABILITY = "business_capability"
    BUSINESS_SERVICE = "business_service"
    APPLICATION = "application"
    TECHNOLOGY = "technology"
    CLOUD_RESOURCE = "cloud_resource"
    SAAS_APPLICATION = "saas_application"
    VENDOR = "vendor"
    CONTRACT = "contract"
    COST_CENTER = "cost_center"
    DEPARTMENT = "department"
    OWNER = "owner"
    PROJECT = "project"
    ENVIRONMENT = "environment"
    BUSINESS_PROCESS = "business_process"
    RISK = "risk"
    RECOMMENDATION = "recommendation"
    APPROVAL = "approval"
    POLICY = "policy"
    EVIDENCE = "evidence"


class RelationshipType(str, Enum):
    """Provider-neutral canonical relationship types."""

    DEPENDS_ON = "depends_on"
    RUNS_ON = "runs_on"
    OWNED_BY = "owned_by"
    SUPPLIED_BY = "supplied_by"
    FUNDS = "funds"
    IMPACTS = "impacts"
    TARGETS = "targets"
    MONITORS = "monitors"
    GOVERNS = "governs"
    APPROVES = "approves"
    EVIDENCES = "evidences"
    ASSOCIATED_WITH = "associated_with"
