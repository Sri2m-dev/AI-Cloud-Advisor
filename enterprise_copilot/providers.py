"""Provider-neutral generation adapters. Providers receive grounded context only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from enterprise_copilot.models import CopilotContext


@dataclass(frozen=True, slots=True)
class ProviderResult:
    text: str
    model_confidence: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class AIProvider(Protocol):
    name: str

    def generate(self, *, system_prompt: str, context: CopilotContext) -> ProviderResult: ...


class MockProvider:
    name = "mock"

    def generate(self, *, system_prompt: str, context: CopilotContext) -> ProviderResult:
        del system_prompt
        if not context.entities:
            return ProviderResult(
                "No governed enterprise entities matched. Unknown remains unknown.", 1.0
            )
        names = ", ".join(str(item["display_name"]) for item in context.entities)
        return ProviderResult(f"Governed results: {names}.", 1.0, 0, 0)


class UnconfiguredProvider:
    def __init__(self, name: str):
        self.name = name

    def generate(self, *, system_prompt: str, context: CopilotContext) -> ProviderResult:
        del system_prompt, context
        raise RuntimeError(f"AI provider '{self.name}' is not configured")


def default_providers():
    names = ("openai", "azure_openai", "aws_bedrock", "anthropic", "gemini")
    return {"mock": MockProvider(), **{name: UnconfiguredProvider(name) for name in names}}
