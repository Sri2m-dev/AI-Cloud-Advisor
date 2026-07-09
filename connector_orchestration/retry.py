"""Connector retry policy contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RetryStrategy(str, Enum):
    NONE = "none"
    IMMEDIATE = "immediate"
    LINEAR = "linear"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    delay_seconds: int = 0
    reason: str = ""


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy used by connector orchestration."""

    strategy: RetryStrategy = RetryStrategy.NONE
    max_attempts: int = 1
    base_delay_seconds: int = 30
    max_delay_seconds: int = 900
    circuit_breaker_failures: int = 5

    def decide(self, attempt: int, consecutive_failures: int = 0) -> RetryDecision:
        if self.strategy == RetryStrategy.NONE:
            return RetryDecision(False, reason="Retry disabled.")
        if attempt >= self.max_attempts:
            return RetryDecision(False, reason="Maximum attempts reached.")
        if self.strategy == RetryStrategy.CIRCUIT_BREAKER and consecutive_failures >= self.circuit_breaker_failures:
            return RetryDecision(False, reason="Circuit breaker open.")
        if self.strategy == RetryStrategy.IMMEDIATE:
            return RetryDecision(True, delay_seconds=0, reason="Immediate retry.")
        if self.strategy == RetryStrategy.LINEAR:
            return RetryDecision(True, delay_seconds=min(self.base_delay_seconds * attempt, self.max_delay_seconds), reason="Linear retry.")
        if self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return RetryDecision(True, delay_seconds=min(self.base_delay_seconds * (2 ** max(0, attempt - 1)), self.max_delay_seconds), reason="Exponential backoff retry.")
        return RetryDecision(False, reason="No retry decision.")
