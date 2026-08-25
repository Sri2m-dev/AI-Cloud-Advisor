"""Bounded capability definitions; registration is not support authority."""

from dataclasses import dataclass

from universal_evidence.capability.models import CapabilityRequirement


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    name: str
    requirements: tuple[CapabilityRequirement, ...]


CAPABILITY_REGISTRY_VERSION = "pue-capability-registry-1"

DEFAULT_CAPABILITY_REGISTRY = (
    CapabilityDefinition("DESCRIBE_AVAILABLE_EVIDENCE", (CapabilityRequirement("COVERAGE"),)),
    CapabilityDefinition("COUNT_EVIDENCE_RECORDS", (CapabilityRequirement("COVERAGE"),)),
    CapabilityDefinition("FILTER_BY_DIMENSION", (CapabilityRequirement("ANY_DIMENSION"),)),
    CapabilityDefinition("TIME_RANGE_ANALYSIS", (CapabilityRequirement("TIME_DIMENSION"),)),
    CapabilityDefinition("MONETARY_TOTAL", (CapabilityRequirement("MONETARY_MEASURE"),)),
    CapabilityDefinition(
        "MONETARY_TOTAL_BY_DIMENSION",
        (
            CapabilityRequirement("MONETARY_MEASURE"),
            CapabilityRequirement("ANY_DIMENSION"),
        ),
    ),
    CapabilityDefinition("CURRENCY_GROUPED_TOTAL", (CapabilityRequirement("CURRENCY_GROUPING"),)),
    CapabilityDefinition("FX_NORMALIZED_TOTAL", (CapabilityRequirement("FX"),)),
    CapabilityDefinition(
        "RESOURCE_INVENTORY",
        (CapabilityRequirement("CONCEPT", "resource.identifier"),),
    ),
    CapabilityDefinition(
        "APPLICATION_INVENTORY",
        (CapabilityRequirement("CONCEPT", "application.name"),),
    ),
    CapabilityDefinition(
        "OWNER_INVENTORY",
        (CapabilityRequirement("CONCEPT", "ownership.owner"),),
    ),
    CapabilityDefinition(
        "REGION_INVENTORY",
        (CapabilityRequirement("CONCEPT", "geography.region"),),
    ),
    CapabilityDefinition(
        "CONTRACT_INVENTORY",
        (CapabilityRequirement("CONCEPT", "contract.identifier"),),
    ),
)
