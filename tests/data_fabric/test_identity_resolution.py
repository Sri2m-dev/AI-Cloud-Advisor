import pytest

from data_fabric.contracts import EnterpriseEntity, EntityIdentity, EntityType
from data_fabric.identity import (
    IdentityValidationError,
    InMemoryIdentityResolver,
    MatchCandidate,
    MatchDecision,
)


def make_entity(**overrides):
    values = {
        "id": "ent-1",
        "canonical_id": "application:checkout",
        "entity_type": EntityType.APPLICATION,
        "name": "Checkout Service",
        "source_system": "servicenow",
        "source_identifier": "app-123",
        "organization_id": "org-1",
        "tenant_id": "tenant-1",
        "metadata": {"aliases": ["checkout api"]},
        "identity": EntityIdentity(
            id="identity-1",
            canonical_id="application:checkout",
            source_system="servicenow",
            source_identifier="app-123",
            organization_id="org-1",
            aliases=["checkout platform"],
        ),
    }
    values.update(overrides)
    return EnterpriseEntity(**values)


def make_candidate(**overrides):
    values = {
        "canonical_id": None,
        "source_system": "servicenow",
        "source_identifier": "app-999",
        "name": "Unknown App",
        "organization_id": "org-1",
    }
    values.update(overrides)
    return MatchCandidate(**values)


def test_resolver_matches_exact_canonical_id() -> None:
    resolver = InMemoryIdentityResolver([make_entity()])

    result = resolver.resolve(make_candidate(canonical_id="application:checkout"))

    assert result.decision is MatchDecision.MATCH
    assert result.confidence_score == 1.0
    assert result.match_reason == "canonical_id"
    assert result.matched_entity is not None
    assert result.matched_entity.id == "ent-1"


def test_resolver_matches_source_identity() -> None:
    resolver = InMemoryIdentityResolver([make_entity()])

    result = resolver.resolve(
        make_candidate(source_system="servicenow", source_identifier="app-123")
    )

    assert result.decision is MatchDecision.MATCH
    assert result.confidence_score == 0.98
    assert result.match_reason == "source_identity"


def test_resolver_matches_normalized_name() -> None:
    resolver = InMemoryIdentityResolver([make_entity()])

    result = resolver.resolve(make_candidate(name="checkout   service"))

    assert result.decision is MatchDecision.MATCH
    assert result.confidence_score == 0.86
    assert result.match_reason == "normalized_name"


def test_resolver_matches_aliases() -> None:
    resolver = InMemoryIdentityResolver([make_entity()])

    from_entity_alias = resolver.resolve(make_candidate(name="Checkout API"))
    from_candidate_alias = resolver.resolve(
        make_candidate(name="Placeholder", aliases=("Checkout Service",))
    )

    assert from_entity_alias.decision is MatchDecision.MATCH
    assert from_entity_alias.match_reason == "candidate_name_entity_alias"
    assert from_candidate_alias.decision is MatchDecision.MATCH
    assert from_candidate_alias.match_reason == "entity_name_candidate_alias"


def test_resolver_detects_duplicates() -> None:
    resolver = InMemoryIdentityResolver(
        [
            make_entity(),
            make_entity(
                id="ent-2",
                canonical_id="application:checkout-shadow",
                source_identifier="app-456",
                metadata={"aliases": ["checkout api"]},
                identity=None,
            ),
        ]
    )

    result = resolver.detect_duplicates(make_candidate(name="Checkout API"))

    assert result.decision is MatchDecision.DUPLICATE
    assert result.confidence_score == 0.82
    assert {entity.id for entity in result.matched_entities} == {"ent-1", "ent-2"}


def test_resolver_returns_explicit_no_match() -> None:
    resolver = InMemoryIdentityResolver([make_entity()])

    result = resolver.resolve(
        make_candidate(
            source_system="aws",
            source_identifier="i-123",
            name="Unrelated Resource",
        )
    )

    assert result.decision is MatchDecision.NO_MATCH
    assert result.confidence_score == 0.0
    assert result.match_reason == "no_match"
    assert result.matched_entity is None
    assert result.matched_entities == ()


def test_resolver_scopes_matches_by_organization() -> None:
    resolver = InMemoryIdentityResolver([make_entity()])

    result = resolver.resolve(
        make_candidate(
            canonical_id="application:checkout",
            source_system="servicenow",
            source_identifier="app-123",
            name="Checkout Service",
            organization_id="org-2",
        )
    )

    assert result.decision is MatchDecision.NO_MATCH


def test_resolver_validates_candidates_and_entities() -> None:
    resolver = InMemoryIdentityResolver()

    with pytest.raises(IdentityValidationError):
        resolver.resolve(make_candidate(source_system=""))

    with pytest.raises(IdentityValidationError):
        resolver.register_entity(make_entity(source_identifier=""))


def test_resolver_returns_copies() -> None:
    resolver = InMemoryIdentityResolver([make_entity()])

    result = resolver.resolve(make_candidate(canonical_id="application:checkout"))
    assert result.matched_entity is not None
    result.matched_entity.metadata["aliases"] = []

    second = resolver.resolve(make_candidate(canonical_id="application:checkout"))
    assert second.matched_entity is not None
    assert second.matched_entity.metadata["aliases"] == ["checkout api"]
