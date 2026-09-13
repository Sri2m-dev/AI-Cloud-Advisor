# Universal governed Ask Nexora release blocker

Date: 2026-09-10

**ASK_NEXORA_UNIVERSAL_QUERY_BLOCKED**

Classification: **CONFIGURATION / EXTERNAL inference prerequisite**, with
required **CODE integration** still outstanding. Browser UAT remains paused.
The complete operator instruction now supersedes the prior narrow fix.

## Current execution trace

| Boundary | Actual implementation | Limitation |
| --- | --- | --- |
| Page and authorization | `pages/enterprise_ai_copilot.py` checks roles and resolves prospect/demo/tenant workspace context before selecting separate answer paths. | There is no shared runtime semantic planner across these paths. |
| Demonstration authority | `DemoAskNexoraService.ask` loads the same synthetic dataset as the Executive Brief. `_intent` selects attention, value, or service risk using words/phrases. | `_value` receives only the payload, not the question or a structured filter. A SaaS constraint is lost before retrieval. No grouping operation is planned. |
| Tenant orchestration | `EnterpriseAIOrchestrator.ask` selects `GovernedAskNexoraService` using `_is_governed_question`; otherwise `route_intent` selects a keyword intent and entity search runs on the prompt or individual tokens. | Retrieval selection precedes any model call. One selected intent controls financial/relationship context; this is not dynamic multi-capability orchestration. |
| Canonical query service | `enterprise_ai_copilot` composes `EnterpriseIntelligenceQueryService` from financial, optimization, registry, and relationship authorities. `GovernedAskNexoraService._canonical_query` selects its query family through substring tests and a fixed dimension map. | Typed authority operations exist, but natural-language runtime planning over their inputs/outputs does not. Unmatched combinations and groupings cannot be decomposed. |
| Prospect evidence | The page selects document closure, governed admission, or prospect answer helpers. Governed measurement builds `build_concept_catalog` from current supported measures and dimensions, then invokes `DeterministicAnalyticalInterpreter`. | The interpreter relies on aliases and patterns. Existing analytical planning supports record count, total, grouping, and time series; it does not supply universal semantic understanding. |
| Answer generation | Demo and governed paths format deterministic results. The remaining tenant path calls `provider.generate(system_prompt, context)` after retrieval. | The generation interface receives neither the original question nor a capability catalogue for planning. `mock` only names matched entities. All named providers in `default_providers` are `UnconfiguredProvider` instances. |
| Conversation | Streamlit stores and displays the last ten user/assistant messages. `CopilotRequest` contains session ID but no prior messages; demo asks receive only question and organization ID. | History is presentation state, not planner context. Follow-up referents and filters are not retained for execution. |

The synthetic data can support bounded SaaS opportunity evidence, but that does
not make the present general opportunity answer a correctly filtered SaaS
answer. The synthetic payload contains no tower/vertical cost attribution;
this particular grouping needs an explicit missing-attribution explanation.
Adding those answers individually would leave the traced limitation intact.

## Exact certification prerequisite

No actual semantic planning provider is implemented on the active Ask path.
The configured request default is `mock`, and named model providers are stubs.
No `ollama`, `llama-server`, or `lms` command was found on PATH; no matching
Ollama/llama/LM Studio process was found; no local inference/model configuration
variable was found in the current environment. These checks do not claim that
every directory or possible runtime on the machine was searched.

An `OPENAI_API_KEY` environment variable name is present. Its value was neither
read nor printed, and the existence of the variable establishes neither a
working model nor authorization to call it. The operator explicitly prohibits
external cloud connections. No such connection was attempted.

The absent inference prerequisite blocks **real-model semantic generalization
certification** under the current no-external-connections constraint. It does
not make typed executor development technically impossible. However, tests
with hand-authored/mock plans would establish executor behavior only, not the
required unseen-language understanding, constraint extraction, or safe
conversational planning. They cannot justify UNIVERSAL_QUERY_CERTIFIED.

## Smallest required remediation

Provide a usable local semantic model/runtime under the existing no-external
boundary, or explicitly revise that boundary for an approved inference
provider. Credentials must remain local. A key by itself does not resolve the
missing planner integration.

Then implement the bounded Ask integration over existing authorities:

- Give the planner the current authorized capability/schema catalogue, original
  question, and conversation context bound to workspace, tenant, user, and role.
- Require structured plans, independently validate capability IDs, operations,
  parameters, filters, relationship traversal, limits, and authorization before
  reads. Never execute model-authored SQL or let the model set tenant scope.
- Invoke existing typed authorities and governed evidence planning/execution;
  preserve filters through every step and compose results with actual source
  provenance, explicit missing mappings, and partial/failure qualifications.
- Exercise the actual model with unseen formulations and adversarial requests,
  alongside deterministic executor/security tests and full release regression.

No question catalogue, synonym expansion, fabricated mappings, or alternative
datastore is a remediation. Existing authority metadata and typed operations
can be reused; the frozen underlying programs need not be reopened.

## Work and verification in this attempt

Read-only execution-path tracing and local runtime/configuration-name checks
completed. Release-status documentation was updated. Product code was not
changed; no substitute mock planner or additional aliases were introduced.

No new focused or full regression certification is claimed. The last completed
regression remains **1,903 passed, 2 skipped, 0 failures**, with its command and
scope recorded in `ASK_NEXORA_UAT_DEFECT.md`; it predates this instruction and
does not certify universal querying. Runtime generalization testing is blocked
by the prerequisite above. No browser testing was performed.

Documentation safety checks: `git diff --check` passed; credential-pattern
scan of the three changed release documents passed (no credential values
printed); no newly staged artifacts or tracked UAT temporary outputs were
found. Retired dependency check:
`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
tests/security/test_rc001_legacy_dependency_manifest.py` — **2 passed**.
These checks do not constitute semantic-planner or universal-query certification.

No Supabase project changes, AWS/Azure calls, client data or credentials,
commit, or push occurred. Existing external certification deferrals remain.

## Remediation progress (2026-09-10)

The provider-neutral planner slice is now implemented in
`enterprise_copilot/semantic_planner.py`. It builds a machine-readable
catalogue from the current governed capability assessment, validates strict
multi-step JSON plans against role and tenant scope, rejects unknown or
unrestricted operations, and executes only explicitly registered capability
handlers. `OpenAIProvider.plan()` uses the Responses API for planner output;
the existing bounded answer-generation path remains provider-neutral.

Offline certification completed with:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
1913 passed, 2 skipped, 0 failures
```

The minimum synthetic live planner call was attempted with the locally present
`OPENAI_API_KEY`, using no Supabase, AWS, Azure, or client data. OpenAI
returned HTTP 401. The key's presence therefore does not establish usable
authorization for this project/model. The release status remains:

**ASK_NEXORA_UNIVERSAL_QUERY_BLOCKED**

Classification: **EXTERNAL_CONFIGURATION**, with production Ask-path wiring
and live semantic generalization certification still pending. Browser UAT
must remain paused. No credential value was read, printed, stored, committed,
or added to documentation.

## Release impact

Ask Nexora is **not release-ready under the universal-query contract**.
Integrated browser UAT stays paused at Ask Nexora. Final release stays pending.
This is the existing release blocker, not a new program or roadmap.
