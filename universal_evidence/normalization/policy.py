"""Versioned representation-only PUE-004 normalization policy."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizationPolicy:
    version: str = "pue-normalization-policy-1"
    trim_strings: bool = True
    unicode_form: str = "NFC"
    collapse_whitespace: bool = False
    supported_date_formats: tuple[str, ...] = ("%Y-%m-%d", "%d/%m/%Y")
    supported_datetime_formats: tuple[str, ...] = (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    )
    true_values: frozenset[str] = frozenset({"true", "yes", "1"})
    false_values: frozenset[str] = frozenset({"false", "no", "0"})
    currency_codes: frozenset[str] = frozenset(
        {"USD", "INR", "EUR", "GBP", "AUD", "CAD", "JPY", "SGD", "AED"}
    )
    allow_cached_formula_values: bool = False
    batch_size: int = 1000

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("normalization policy version is required")
        if self.batch_size <= 0:
            raise ValueError("normalization batch size must be positive")
