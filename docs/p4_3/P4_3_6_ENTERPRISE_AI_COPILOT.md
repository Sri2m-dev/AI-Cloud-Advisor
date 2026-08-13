# P4.3.6 Enterprise AI Copilot

The Copilot is a provider-neutral orchestration layer, not a data, query, search,
recommendation, or execution authority. Its chain is UI → AI Orchestrator →
Enterprise Search → Enterprise Intelligence → governed P4.3/P4.2/P3 sources.
Providers receive only the bounded `CopilotContext`; they cannot access services
or repositories.

Contracts separate request, context, evidence, citations, response, and
short-lived session history. Deterministic routing covers financial, inventory,
relationship/dependency, ownership, risk, classification, health, change,
search, and unknown intents before provider invocation. Prompts are versioned in
one registry (`grounded-answer-v1`).

The provider interface includes Mock plus fail-closed adapters for OpenAI, Azure
OpenAI, AWS Bedrock, Anthropic, and Gemini. No external provider is configured or
called in this milestone. Enterprise confidence remains separate from provider
model confidence. Citations reference canonical governed sources with confidence
and freshness; missing owner/business context remains explicitly UNKNOWN.

Policy rejects mutation, approval, execution, credentials/secrets, raw SQL, and
repository-access prompts. Tenant and active-persona equality are mandatory.
Evidence is retrieved only for administrator/auditor personas, reusing Search
authorization. Session history is Streamlit-session-local, bounded to ten
messages, and never persisted or learned.

Metrics capture latency, provider, routing/retrieval/grounding time, token counts,
citations, and policy blocks without logging prompts. Browser acceptance must
cover Executive, CIO, Finance, Auditor, Operations, Admin, citations/evidence,
and UNKNOWN behavior. No migrations, cache, permanent memory, production access,
or runtime-configuration changes are introduced.
