# Ask Nexora integrated UAT defect

Date: 2026-09-10

Status: **REOPENED / UNIVERSAL_GOVERNED_ASK_RELEASE_BLOCKER**.
This continues the existing integrated UAT gate.

## Subsequent operator UAT decision

The prior ASK_NEXORA_UAT_DEFECT_FIXED designation describes only the narrow
correction below and is not accepted as final Ask Nexora certification.
Its automated result (1,903 passed, 2 skipped) remains historical evidence.

Operator-reported observations:

1. "What is the total savings?" returned a governed savings response.
2. "What is the SaaS license savings?" returned substantially the same generic
   opportunity narrative instead of restricting evidence to SaaS/licensing.
3. "Can you provide the total cost split for each tower/vertical" returned
   generic UNKNOWN without identifying missing dimension or mapping authority.

Browser UAT is stopped at the operator's request. Do not add question aliases,
intents, or answer templates as the solution. The required direction is dynamic
natural-language understanding, governed capability discovery, validated query
planning, scoped execution, evidence combination where authorized, and grounded
answer composition. SaaS requests must constrain retrieval; unavailable
groupings must explain the specific missing dimension/mapping. UNKNOWN,
provenance, and tenant isolation must remain intact.

The complete "NEXORA RELEASE BLOCKER — UNIVERSAL GOVERNED ASK NEXORA"
instruction has now been received. The execution trace and concrete inference
prerequisite are recorded in `UNIVERSAL_GOVERNED_ASK_BLOCKER.md`.
Current result: **ASK_NEXORA_UNIVERSAL_QUERY_BLOCKED**. The prior correction and
regression below remain historical evidence, not universal-query certification.

## Evidence and cause

The operator reported that Ask Nexora rendered correctly and returned UNKNOWN
without fabricated answers or citations for an unsupported revenue forecast.
Cost-reduction and business-service technology-risk questions also returned
UNKNOWN despite evidence in the synthetic Executive Brief.

The existing page explicitly routes the synthetic workspace to
`DemoAskNexoraService`, before production copilot execution. Therefore the
production `EnterpriseIntelligenceQueryService` is not the failing retrieval
path and requires no change for this defect. The demonstration interpreter
matched only attention phrases and the substrings `saving`, `opportunity`, and
`realized value`. It lacked cost-reduction vocabulary, plural opportunities,
and a service-risk answer rule.

The existing value answer also mislabeled the identified $12.4M as qualified.
The shared demonstration authority's savings waterfall records $9.6M as
evidence-qualified, separately from identified and verified realized value.

## Correction

- Token-based intent vocabulary accepts equivalent cost-reduction/opportunity
  and business-service risk/health/intervention questions.
- Financial answers use the existing shared savings waterfall and portfolio
  rationalization decision records. No question-specific figures or answers
  are hard-coded. Identified annual opportunity, qualified opportunity, and
  realized value remain separate; quarterly timing and amounts remain UNKNOWN.
- Risk answers order the existing service-health records by recorded severity,
  explicitly limiting the ranking to listed services. No financial-loss or
  future-outcome inference is added.
- Every returned fact retains the dataset source, classification, organization,
  as-of timestamp, and source record in provenance. Missing required authority
  returns UNKNOWN with no facts or citations.
- Forecast requests, including mixed savings/revenue requests, remain UNKNOWN.
- Ask now checks the requested organization against the loaded dataset identity
  or its existing registered demo organization ID; another `demo-` prefix is
  insufficient. Demo mode and explicit organization remain required.

No CEO-specific branch, Executive Brief duplication, production query change,
new architecture, or default-tenant fallback was introduced.

## Validation

Focused Ask/Executive intelligence run: **85 passed**. Includes new semantic
variants, source-driven changed values/ranking, missing evidence, forecast
rejection, disabled demo mode, missing tenant, and cross-tenant rejection tests.
Ruff checks pass for both changed Python files.

The first full regression attempt encountered pytest temporary-directory
permission errors and was interrupted. A diagnostic run reproduced the error
before test execution; the affected module passed all 7 tests using a fresh
workspace temporary directory. The replacement full run disables cache and
uses a fresh workspace `--basetemp`, with results captured in
`.tmp/ask-nexora-uat-regression.log` and `.tmp/ask-nexora-uat-regression.xml`.

That run completed with 1,902 passed, 2 skipped, and one inventory mismatch:
the literal cost plural in the intent vocabulary was scanned as a database
object reference. A singular/plural regex now expresses the same vocabulary
without that false reference; the frozen database inventory was not changed.

Final full regression: **1,903 passed, 2 skipped, 0 failures** (82.29 seconds).
Command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp
<fresh workspace .tmp directory> --junitxml=.tmp/ask-nexora-uat-regression.xml`.
The log and XML above contain this final run. Ruff and scoped `git diff --check`
pass. No automated browser re-test is claimed.

## Prior operator re-test scope (superseded; browser UAT now stopped)

Re-test only these cases in the same governed synthetic workspace:

1. "Where can we reduce costs this quarter?" — bounded opportunity answer with
   $12.4M annual identified, $9.6M qualified, $3.1M realized, and the $4.2M SaaS
   consolidation decision; citations present; quarterly timing remains UNKNOWN.
2. "Which business services have the highest technology risk?" — Digital
   Checkout (Critical, health 61), then Payments Authorization (High, health 66),
   from the listed service records with provenance and scope limitations.
3. "What will our exact revenue be next quarter?" — UNKNOWN; no fabricated
   answer, forecast, facts, or citations.

No cloud provisioning or live certification, commit, or push is part of this
fix. External gate deferrals remain unchanged. Browser acceptance remains with
the operator; do not restart the integrated UAT gate.
