"""Deterministic PUE-008 natural-language analytical intent interpretation."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from datetime import datetime, timezone

from universal_evidence.aggregation import FilterOperator, TimeBucket
from universal_evidence.interpretation.aliases import (
    DIMENSION_ALIASES,
    MEASURE_ALIASES,
    VALUE_ALIASES,
)
from universal_evidence.interpretation.fingerprint import fingerprint
from universal_evidence.interpretation.literals import parse_date_phrase, parse_literal
from universal_evidence.interpretation.models import (
    AnalyticalConceptCatalog,
    ConfidenceBand,
    IntentCandidate,
    InterpretationProvenance,
    InterpretationReason,
    InterpretationStatus,
    NaturalLanguageInterpretationResult,
    NaturalLanguageQuestion,
)
from universal_evidence.interpretation.patterns import (
    COUNT_RECORD_PATTERNS,
    DISTINCT_COUNT_TERMS,
    TIME_PATTERNS,
    UNSUPPORTED_OPERATION_TERMS,
)
from universal_evidence.interpretation.policy import InterpretationPolicy
from universal_evidence.planning import (
    AnalyticalIntent,
    AnalyticalIntentType,
    IntentFilter,
)


class DeterministicAnalyticalInterpreter:
    def __init__(
        self,
        *,
        policy: InterpretationPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.policy = policy or InterpretationPolicy()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def interpret(
        self,
        question: NaturalLanguageQuestion,
        catalog: AnalyticalConceptCatalog,
    ) -> NaturalLanguageInterpretationResult:
        canonical = self._canonicalize(question.question)
        if question.scope != catalog.scope:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.REJECTED,
                (InterpretationReason.GOVERNED_CONCEPT_NOT_AVAILABLE,),
                ("Question scope does not match the governed catalog scope.",),
            )
        if question.question_version != self.policy.question_version:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.REJECTED,
                (InterpretationReason.QUESTION_UNSUPPORTED,),
                ("Question contract version is not supported.",),
            )
        if not canonical:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.REJECTED,
                (InterpretationReason.QUESTION_EMPTY,),
                ("Question is empty.",),
            )
        if len(question.question) > self.policy.maximum_question_length:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.REJECTED,
                (InterpretationReason.QUESTION_TOO_LONG,),
                ("Question exceeds the bounded interpretation length.",),
            )
        if "\x00" in question.question:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.REJECTED,
                (InterpretationReason.QUESTION_UNSAFE,),
                ("Question contains unsupported binary content.",),
            )
        unsupported = next(
            (label for term, label in UNSUPPORTED_OPERATION_TERMS.items() if term in canonical),
            None,
        )
        if unsupported is not None:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.UNSUPPORTED,
                (InterpretationReason.UNSUPPORTED_OPERATION,),
                (f"The question requests unsupported analytical behavior: {unsupported}.",),
            )
        if any(term in canonical for term in DISTINCT_COUNT_TERMS):
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.UNSUPPORTED,
                (InterpretationReason.UNSUPPORTED_INTENT_SHAPE,),
                ("Distinct dimension counting is not a supported intent.",),
            )
        if any(pattern in canonical for pattern in COUNT_RECORD_PATTERNS):
            return self._interpreted(
                question,
                canonical,
                catalog,
                AnalyticalIntentType.COUNT_RECORDS,
                None,
                (),
                None,
                (),
                None,
                ("A bounded record-count phrase matched COUNT_RECORDS.",),
                (InterpretationReason.QUESTION_INTERPRETED,),
                0.98,
            )

        measures = self._measure_matches(canonical, catalog)
        if not measures:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.INSUFFICIENT_CONTEXT,
                (InterpretationReason.GOVERNED_CONCEPT_NOT_AVAILABLE,),
                ("No governed measure matches the analytical language.",),
            )
        if len(measures) > 1:
            candidates = tuple(
                self._candidate(
                    AnalyticalIntentType.TOTAL_MEASURE,
                    concept,
                    (),
                    None,
                    None,
                    0.6,
                    (f"Measure term may refer to {concept}.",),
                    (),
                )
                for concept in measures
            )
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.AMBIGUOUS,
                (InterpretationReason.MULTIPLE_MEASURES_PLAUSIBLE,),
                tuple(f"Governed measure candidate: {item}." for item in measures),
                candidates=candidates,
                score=0.6,
            )
        measure = measures[0]
        available_dimensions = {item.semantic_concept_id for item in catalog.dimensions}
        requested_dimensions = {
            concept
            for alias, concept in DIMENSION_ALIASES.items()
            if re.search(rf"\bby\s+{re.escape(alias)}\b", canonical)
        }
        if requested_dimensions - available_dimensions:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.UNSUPPORTED,
                (InterpretationReason.GOVERNED_CONCEPT_NOT_AVAILABLE,),
                ("A requested grouping concept is not governed in this catalog.",),
            )
        grouped_dimensions = self._grouped_dimension_matches(canonical, catalog)
        time_bucket = self._time_bucket(canonical)
        time_dimensions = tuple(item for item in catalog.dimensions if item.is_time_dimension)
        if grouped_dimensions and time_bucket is not None:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.UNSUPPORTED,
                (InterpretationReason.UNSUPPORTED_INTENT_SHAPE,),
                ("Grouping and time-series semantics cannot be combined by PUE-007.",),
            )
        if len(grouped_dimensions) > 1:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.AMBIGUOUS,
                (InterpretationReason.MULTIPLE_DIMENSIONS_PLAUSIBLE,),
                tuple(f"Governed dimension candidate: {item}." for item in grouped_dimensions),
                score=0.55,
            )
        if time_bucket is not None:
            if len(time_dimensions) != 1:
                status = (
                    InterpretationStatus.AMBIGUOUS
                    if time_dimensions
                    else InterpretationStatus.INSUFFICIENT_CONTEXT
                )
                reason = (
                    InterpretationReason.MULTIPLE_DIMENSIONS_PLAUSIBLE
                    if time_dimensions
                    else InterpretationReason.GOVERNED_CONCEPT_NOT_AVAILABLE
                )
                return self._result(
                    question,
                    canonical,
                    catalog,
                    status,
                    (reason,),
                    ("A unique governed time dimension is required.",),
                )
            return self._interpreted(
                question,
                canonical,
                catalog,
                AnalyticalIntentType.TIME_SERIES_MEASURE,
                measure,
                (),
                time_dimensions[0].semantic_concept_id,
                (),
                time_bucket,
                (
                    f"Measure language matched {measure}.",
                    f"Time language selected {time_bucket.value} using "
                    f"{time_dimensions[0].semantic_concept_id}.",
                ),
                (
                    InterpretationReason.QUESTION_INTERPRETED,
                    InterpretationReason.MEASURE_TERM_MATCHED,
                    InterpretationReason.TIME_TERM_MATCHED,
                ),
                0.92,
            )
        filters, filter_reasons, filter_explanations, filter_error = self._filters(
            canonical, catalog
        )
        if filter_error is not None:
            return self._result(
                question,
                canonical,
                catalog,
                InterpretationStatus.UNSUPPORTED,
                (filter_error,),
                tuple(filter_explanations),
            )
        if grouped_dimensions:
            dimension = grouped_dimensions[0]
            return self._interpreted(
                question,
                canonical,
                catalog,
                AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
                measure,
                (dimension,),
                None,
                filters,
                None,
                (f"Measure language matched {measure}.", f"'by' matched {dimension}."),
                (
                    InterpretationReason.QUESTION_INTERPRETED,
                    InterpretationReason.MEASURE_TERM_MATCHED,
                    InterpretationReason.DIMENSION_TERM_MATCHED,
                ),
                0.94,
            )
        return self._interpreted(
            question,
            canonical,
            catalog,
            AnalyticalIntentType.TOTAL_MEASURE,
            measure,
            (),
            None,
            filters,
            None,
            (f"Measure language matched {measure}.", *filter_explanations),
            (
                InterpretationReason.QUESTION_INTERPRETED,
                InterpretationReason.MEASURE_TERM_MATCHED,
                *filter_reasons,
            ),
            0.93 if not filters else 0.88,
        )

    def _measure_matches(self, canonical, catalog):
        concepts = tuple(item.semantic_concept_id for item in catalog.measures)
        matched = any(re.search(rf"\b{re.escape(alias)}\b", canonical) for alias in MEASURE_ALIASES)
        if not matched:
            return ()
        if "total" in canonical:
            return tuple(item for item in concepts if item == "financial.cost.total")
        if "monthly" in canonical and "trend" not in canonical:
            return tuple(item for item in concepts if item == "financial.cost.monthly")
        return tuple(item for item in concepts if item.startswith("financial.cost."))

    def _grouped_dimension_matches(self, canonical, catalog):
        available = {item.semantic_concept_id for item in catalog.dimensions}
        matches = []
        for alias, concept in DIMENSION_ALIASES.items():
            if re.search(rf"\bby\s+{re.escape(alias)}\b", canonical) and concept in available:
                matches.append(concept)
        return tuple(sorted(set(matches)))

    @staticmethod
    def _time_bucket(canonical):
        for phrase, bucket in TIME_PATTERNS.items():
            if phrase in canonical:
                return TimeBucket(bucket)
        return None

    def _filters(self, canonical, catalog):
        dimensions = {item.semantic_concept_id: item for item in catalog.dimensions}
        results = []
        reasons = []
        explanations = []
        for literal, (concept, normalized) in VALUE_ALIASES.items():
            if re.search(rf"\b{re.escape(literal)}\b", canonical):
                dimension = dimensions.get(concept)
                if dimension is None:
                    continue
                dimension_aliases = tuple(
                    alias for alias, target in DIMENSION_ALIASES.items() if target == concept
                )
                if any(
                    re.search(rf"\b{re.escape(alias)}\s+in\b", canonical)
                    for alias in dimension_aliases
                ):
                    continue
                if not dimension.filterable or "EQUALS" not in dimension.allowed_filter_operators:
                    return (), (), explanations, InterpretationReason.FILTER_VALUE_INVALID
                results.append(IntentFilter(concept, FilterOperator.EQUALS, normalized))
                reasons.extend(
                    (
                        InterpretationReason.FILTER_TERM_MATCHED,
                        InterpretationReason.FILTER_VALUE_TYPED,
                    )
                )
                explanations.append(
                    f"'{literal}' became a literal {concept} string filter; no entity was resolved."
                )
        for alias, concept in DIMENSION_ALIASES.items():
            dimension = dimensions.get(concept)
            if dimension is None or not dimension.filterable:
                continue
            date_match = re.search(
                rf"\b{re.escape(alias)}\s+(before|after)\s+([a-z]+\s+\d{{1,2}},?\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})",
                canonical,
            )
            if date_match:
                operator = (
                    FilterOperator.DATE_TO
                    if date_match.group(1) == "before"
                    else FilterOperator.DATE_FROM
                )
                if operator.value not in dimension.allowed_filter_operators:
                    return (), (), explanations, InterpretationReason.FILTER_VALUE_INVALID
                value = parse_date_phrase(
                    date_match.group(2).title(), dimension.normalized_value_type
                )
                if value is None:
                    return (), (), explanations, InterpretationReason.FILTER_VALUE_INVALID
                results.append(IntentFilter(concept, operator, value))
                reasons.extend(
                    (
                        InterpretationReason.FILTER_TERM_MATCHED,
                        InterpretationReason.FILTER_VALUE_TYPED,
                    )
                )
                explanations.append(
                    f"A typed {dimension.normalized_value_type.value} filter was parsed."
                )
            bool_match = re.search(rf"\b{re.escape(alias)}\s+(?:is|equals)\s+(\w+)\b", canonical)
            if bool_match and dimension.normalized_value_type.value == "BOOLEAN":
                value = parse_literal(bool_match.group(1), dimension.normalized_value_type)
                if value is None:
                    return (), (), explanations, InterpretationReason.FILTER_VALUE_INVALID
                if "EQUALS" not in dimension.allowed_filter_operators:
                    return (), (), explanations, InterpretationReason.FILTER_VALUE_INVALID
                results.append(IntentFilter(concept, FilterOperator.EQUALS, value))
                reasons.extend(
                    (
                        InterpretationReason.FILTER_TERM_MATCHED,
                        InterpretationReason.FILTER_VALUE_TYPED,
                    )
                )
                explanations.append("A bounded Boolean literal was typed explicitly.")
            in_match = re.search(rf"\b{re.escape(alias)}\s+in\s+([^?.]+)", canonical)
            if in_match:
                if "IN" not in dimension.allowed_filter_operators:
                    return (), (), explanations, InterpretationReason.FILTER_VALUE_INVALID
                members = tuple(
                    part.strip()
                    for part in re.split(r"\s*(?:,|\band\b)\s*", in_match.group(1))
                    if part.strip()
                )
                values = tuple(
                    (
                        VALUE_ALIASES[member.lower()][1]
                        if member.lower() in VALUE_ALIASES
                        and VALUE_ALIASES[member.lower()][0] == concept
                        else parse_literal(member, dimension.normalized_value_type)
                    )
                    for member in members
                )
                if not values or any(value is None for value in values):
                    return (), (), explanations, InterpretationReason.FILTER_VALUE_INVALID
                results.append(IntentFilter(concept, FilterOperator.IN, values))
                reasons.extend(
                    (
                        InterpretationReason.FILTER_TERM_MATCHED,
                        InterpretationReason.FILTER_VALUE_TYPED,
                    )
                )
                explanations.append("An IN list was typed against governed dimension metadata.")
        unique = {fingerprint(item): item for item in results}
        return (
            tuple(unique[key] for key in sorted(unique)),
            tuple(dict.fromkeys(reasons)),
            explanations,
            None,
        )

    def _interpreted(
        self,
        question,
        canonical,
        catalog,
        intent_type,
        measure,
        dimensions,
        time_dimension,
        filters,
        time_bucket,
        explanation,
        reasons,
        score,
    ):
        candidate = self._candidate(
            intent_type,
            measure,
            dimensions,
            time_dimension,
            time_bucket.value if time_bucket else None,
            score,
            explanation,
            (),
        )
        intent_identity = fingerprint(question.question_id, catalog.fingerprint, candidate, filters)
        structured = AnalyticalIntent(
            "interpreted-intent-" + intent_identity[:24],
            question.scope,
            intent_type,
            measure,
            dimensions,
            time_dimension,
            filters,
            time_bucket,
            None,
            question.caller_id,
            question.caller_type,
            catalog.capability_assessment_id,
            None,
            "pue-analytical-intent-1",
            question.created_at,
        )
        return self._result(
            question,
            canonical,
            catalog,
            InterpretationStatus.INTERPRETED,
            reasons,
            explanation,
            structured,
            (candidate,),
            score,
        )

    def _candidate(
        self,
        intent_type,
        measure,
        dimensions,
        time_dimension,
        time_bucket,
        score,
        supporting,
        contradicting,
    ):
        identity = fingerprint(
            intent_type,
            measure,
            dimensions,
            time_dimension,
            time_bucket,
            score,
            supporting,
            contradicting,
            self.policy.version,
        )
        return IntentCandidate(
            intent_type,
            measure,
            dimensions,
            time_dimension,
            time_bucket,
            score,
            supporting,
            contradicting,
            identity,
        )

    def _result(
        self,
        question,
        canonical,
        catalog,
        status,
        reasons,
        explanation,
        primary=None,
        candidates=(),
        score=0.0,
    ):
        provenance = InterpretationProvenance(
            question.question_id,
            catalog.capability_assessment_id,
            catalog.fingerprint,
            question.scope,
            self.policy.interpreter_name,
            self.policy.interpreter_version,
            self.policy.alias_registry_version,
            self.policy.pattern_registry_version,
            self.policy.literal_policy_version,
            self.policy.version,
        )
        identity = fingerprint(
            question.question,
            canonical,
            question.scope,
            catalog.fingerprint,
            status,
            primary,
            candidates,
            score,
            reasons,
            explanation,
            provenance,
        )
        return NaturalLanguageInterpretationResult(
            "interpretation-" + identity[:24],
            question.question,
            canonical,
            question.scope,
            status,
            primary,
            candidates,
            score,
            self._band(score),
            reasons,
            explanation,
            provenance,
            identity,
            self.clock(),
        )

    @staticmethod
    def _canonicalize(value):
        normalized = unicodedata.normalize("NFKC", value)
        return re.sub(r"\s+", " ", normalized).strip().lower()

    @staticmethod
    def _band(score):
        if score >= 0.85:
            return ConfidenceBand.HIGH
        if score >= 0.65:
            return ConfidenceBand.MEDIUM
        if score > 0:
            return ConfidenceBand.LOW
        return ConfidenceBand.INSUFFICIENT
