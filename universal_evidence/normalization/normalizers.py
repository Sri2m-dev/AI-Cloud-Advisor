"""Representation-only primitive normalizers."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from universal_evidence.normalization.models import NormalizationStatus
from universal_evidence.normalization.policy import NormalizationPolicy
from universal_evidence.normalization.warnings import NormalizationWarning

NormalizedResult = tuple[Any, str | None, NormalizationStatus, tuple[NormalizationWarning, ...]]


def normalize_string(value: Any, policy: NormalizationPolicy) -> NormalizedResult:
    if not isinstance(value, str):
        return (
            None,
            None,
            NormalizationStatus.INVALID,
            (NormalizationWarning.UNSUPPORTED_VALUE_TYPE,),
        )
    normalized = unicodedata.normalize(policy.unicode_form, value)
    if policy.trim_strings:
        normalized = normalized.strip()
    if policy.collapse_whitespace:
        normalized = re.sub(r"\s+", " ", normalized)
    status = (
        NormalizationStatus.UNCHANGED if normalized == value else NormalizationStatus.NORMALIZED
    )
    return normalized, "STRING", status, ()


def normalize_decimal(value: Any, policy: NormalizationPolicy) -> NormalizedResult:
    del policy
    if isinstance(value, bool):
        parsed = None
    elif isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int):
        parsed = Decimal(value)
    elif isinstance(value, float):
        parsed = Decimal(str(value))
    elif isinstance(value, str):
        try:
            parsed = Decimal(value.strip().replace(",", ""))
        except InvalidOperation:
            parsed = None
    else:
        parsed = None
    if parsed is None or not parsed.is_finite():
        return None, None, NormalizationStatus.INVALID, (NormalizationWarning.NUMERIC_PARSE_FAILED,)
    return parsed, "DECIMAL", NormalizationStatus.NORMALIZED, ()


def normalize_integer(value: Any, policy: NormalizationPolicy) -> NormalizedResult:
    parsed, _, status, warnings = normalize_decimal(value, policy)
    if status is NormalizationStatus.INVALID or parsed != parsed.to_integral_value():
        return None, None, NormalizationStatus.INVALID, (NormalizationWarning.NUMERIC_PARSE_FAILED,)
    return int(parsed), "INTEGER", NormalizationStatus.NORMALIZED, warnings


def normalize_date(value: Any, policy: NormalizationPolicy) -> NormalizedResult:
    if isinstance(value, datetime):
        return value.date(), "DATE", NormalizationStatus.NORMALIZED, ()
    if isinstance(value, date):
        return value, "DATE", NormalizationStatus.UNCHANGED, ()
    if isinstance(value, str):
        for date_format in policy.supported_date_formats:
            try:
                return (
                    datetime.strptime(value.strip(), date_format).date(),
                    "DATE",
                    NormalizationStatus.NORMALIZED,
                    (),
                )
            except ValueError:
                continue
    return None, None, NormalizationStatus.INVALID, (NormalizationWarning.DATE_PARSE_FAILED,)


def normalize_datetime(value: Any, policy: NormalizationPolicy) -> NormalizedResult:
    if isinstance(value, datetime):
        return value, "DATETIME", NormalizationStatus.UNCHANGED, ()
    if isinstance(value, str):
        for date_format in policy.supported_datetime_formats:
            try:
                return (
                    datetime.strptime(value.strip(), date_format),
                    "DATETIME",
                    NormalizationStatus.NORMALIZED,
                    (),
                )
            except ValueError:
                continue
    return None, None, NormalizationStatus.INVALID, (NormalizationWarning.DATETIME_PARSE_FAILED,)


def normalize_boolean(value: Any, policy: NormalizationPolicy) -> NormalizedResult:
    if isinstance(value, bool):
        return value, "BOOLEAN", NormalizationStatus.UNCHANGED, ()
    lexical = str(value).strip().lower() if isinstance(value, (str, int)) else ""
    if lexical in policy.true_values:
        return True, "BOOLEAN", NormalizationStatus.NORMALIZED, ()
    if lexical in policy.false_values:
        return False, "BOOLEAN", NormalizationStatus.NORMALIZED, ()
    return None, None, NormalizationStatus.INVALID, (NormalizationWarning.BOOLEAN_PARSE_FAILED,)


def normalize_currency(value: Any, policy: NormalizationPolicy) -> NormalizedResult:
    if not isinstance(value, str):
        return None, None, NormalizationStatus.INVALID, (NormalizationWarning.CURRENCY_UNKNOWN,)
    code = value.strip().upper()
    if code not in policy.currency_codes:
        return None, None, NormalizationStatus.INVALID, (NormalizationWarning.CURRENCY_UNKNOWN,)
    status = NormalizationStatus.UNCHANGED if code == value else NormalizationStatus.NORMALIZED
    return code, "CURRENCY_CODE", status, ()
