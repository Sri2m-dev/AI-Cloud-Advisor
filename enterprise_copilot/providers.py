"""Provider-neutral generation adapters. Providers receive grounded context only."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping, Protocol

import httpx

from data_fabric.foundation import TenantContext
from enterprise_copilot.models import CopilotContext
from enterprise_copilot.semantic_planner import CapabilityDescriptor


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


class OpenAIProvider:
    """OpenAI Responses API adapter for bounded, already-grounded context."""

    name = "openai"

    def __init__(self, *, api_key=None, model=None, client=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6")
        self.client = client or httpx.Client(
            base_url="https://api.openai.com/v1", timeout=60.0
        )

    def generate(self, *, system_prompt: str, context: CopilotContext) -> ProviderResult:
        if not self.api_key:
            raise RuntimeError("AI provider 'openai' requires OPENAI_API_KEY")
        response = self.client.post(
            "/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "instructions": (
                    f"{system_prompt}\n"
                    "The context below is the complete authorized evidence. "
                    "Do not infer facts that are not present, and preserve UNKNOWN."
                ),
                "input": json.dumps(
                    {
                        "question": context.question,
                        "intent": context.intent,
                        "entities": context.entities,
                        "evidence": context.evidence,
                        "unknowns": context.unknowns,
                        "policy_version": context.policy_version,
                    },
                    default=lambda value: asdict(value) if is_dataclass(value) else str(value),
                ),
            },
        )
        if response.is_error:
            raise RuntimeError(f"OpenAI Responses API failed ({response.status_code})")
        payload = response.json()
        text = payload.get("output_text") or _response_text(payload)
        if not text:
            raise RuntimeError("OpenAI Responses API returned no answer")
        usage = payload.get("usage") or {}
        return ProviderResult(
            text,
            None,
            int(usage.get("input_tokens", 0)),
            int(usage.get("output_tokens", 0)),
        )

    def plan(
        self,
        *,
        question: str,
        catalogue: tuple[CapabilityDescriptor, ...],
        scope: TenantContext,
        conversation: tuple[Mapping[str, str], ...] = (),
    ) -> Mapping[str, Any]:
        if not self.api_key:
            raise RuntimeError("AI provider 'openai' requires OPENAI_API_KEY")
        response = self.client.post(
            "/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "instructions": (
                    "Return one JSON object matching the requested governed plan. "
                    "Use only capability IDs and operations from the catalogue. "
                    "Never return SQL, code, credentials, or a tenant scope. "
                    "If the catalogue cannot support the requested conclusion, "
                    "select its explicit UNKNOWN capability instead of inferring facts. "
                    "Never invent dimensions, measures, filters, or capability IDs "
                    "that are absent from the catalogue."
                ),
                "input": json.dumps(
                    {
                        "question": question,
                        "conversation": conversation,
                        "scope": {
                            "organization_id": scope.organization_id,
                            "tenant_id": scope.tenant_id,
                        },
                        "catalogue": catalogue,
                    },
                    default=lambda value: asdict(value) if is_dataclass(value) else str(value),
                ),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "governed_semantic_plan",
                        "strict": True,
                        "schema": _semantic_plan_schema(),
                    }
                },
            },
        )
        if response.is_error:
            request_id = response.headers.get("x-request-id") or "absent"
            raise RuntimeError(
                f"OpenAI Responses API failed ({response.status_code}; request_id={request_id})"
            )
        payload = response.json()
        text = payload.get("output_text") or _response_text(payload)
        if not text:
            raise RuntimeError("OpenAI Responses API returned no plan")
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenAI planner returned invalid JSON") from error


def _semantic_plan_schema():
    step = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "step_id": {"type": "string", "pattern": "^(step_)?[a-z0-9_]{1,40}$"},
            "capability_id": {"type": "string"},
            "operation": {"type": "string"},
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": ["string", "null"]},
                    "result_limit": {"type": ["integer", "null"]},
                    "filter": {"type": ["string", "null"]},
                    "value": {"type": ["string", "number", "boolean", "null"]},
                },
                "required": ["query", "result_limit", "filter", "value"],
            },
            "depends_on": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["step_id", "capability_id", "operation", "parameters", "depends_on"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "interpretation": {"type": "string"},
            "entities": {"type": "array", "items": {"type": "string"}},
            "measures": {"type": "array", "items": {"type": "string"}},
            "dimensions": {"type": "array", "items": {"type": "string"}},
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "dimension": {"type": "string"},
                        "operator": {"type": "string"},
                        "value": {"type": ["string", "number", "boolean", "null"]},
                    },
                    "required": ["dimension", "operator", "value"],
                },
            },
            "time_range": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "start": {"type": "string"},
                            "end": {"type": "string"},
                        },
                        "required": ["start", "end"],
                    },
                ]
            },
            "grouping": {"type": "array", "items": {"type": "string"}},
            "ordering": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "field": {"type": "string"},
                            "direction": {"type": "string"},
                        },
                        "required": ["field", "direction"],
                    },
                ]
            },
            "steps": {"type": "array", "items": step, "minItems": 1, "maxItems": 8},
            "synthesis": {"type": "string"},
        },
        "required": [
            "interpretation",
            "entities",
            "measures",
            "dimensions",
            "filters",
            "time_range",
            "grouping",
            "ordering",
            "steps",
            "synthesis",
        ],
    }


def _response_text(payload):
    parts = []
    for item in payload.get("output", ()):
        for content in item.get("content", ()):
            if content.get("type") in {"output_text", "text"}:
                parts.append(content.get("text", ""))
    return "".join(parts).strip()


class UnconfiguredProvider:
    def __init__(self, name: str):
        self.name = name

    def generate(self, *, system_prompt: str, context: CopilotContext) -> ProviderResult:
        del system_prompt, context
        raise RuntimeError(f"AI provider '{self.name}' is not configured")


def default_providers():
    names = ("openai", "azure_openai", "aws_bedrock", "anthropic", "gemini")
    return {
        "mock": MockProvider(),
        "openai": OpenAIProvider(),
        **{name: UnconfiguredProvider(name) for name in names if name != "openai"},
    }
