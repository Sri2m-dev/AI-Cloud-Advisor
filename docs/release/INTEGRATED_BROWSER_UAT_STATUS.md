# Integrated browser/UAT gate

Decision date: 2026-09-10

## Release state

| Gate | State |
| --- | --- |
| RC-001 | COMPLETE / FROZEN |
| Local release | CERTIFIED / FROZEN |
| AWS connector preparation | READY / FROZEN |
| Azure connector preparation | READY / FROZEN |
| Supabase staging | DEFERRED_EXTERNAL_COST |
| AWS live certification | DEFERRED_EXTERNAL_ENVIRONMENT |
| Azure live certification | DEFERRED_EXTERNAL_ENVIRONMENT |
| REL-C1 | EXTERNAL_RELEASE_BLOCKER |
| Integrated browser/UAT | STOPPED / UNIVERSAL GOVERNED ASK RELEASE BLOCKER |
| Final release | PENDING |

Universal Ask outcome: **ASK_NEXORA_UNIVERSAL_QUERY_BLOCKED**. See
`UNIVERSAL_GOVERNED_ASK_BLOCKER.md` for the execution trace, unavailable semantic
inference prerequisite, and required Ask integration. Operator browser UAT
remains paused; prior regression success does not establish universal querying.

The frozen gate states above carry forward the existing release evidence and
operator decision; they are not new certification results from this attempt.

## External certification decision

AWS preparation remains AWS_LIVE_CERTIFICATION_READY. Execution is
DEFERRED_EXTERNAL_ENVIRONMENT because the operator reports that no dedicated
non-production AWS account is currently available. Product defect: NO.
Connector defect: NO. Code change required: NO for this deferral.

Azure preparation remains AZURE_LIVE_CERTIFICATION_READY. Live execution is
DEFERRED_EXTERNAL_ENVIRONMENT per the operator's decision; a suitable safe
non-production subscription has not been supplied for certification.

Do not configure AWS credentials, create permanent access keys, provision paid
cloud environments, or use client environments to close these gates. Supabase
staging remains deferred for external cost. The existing connector permission
contract remains in LIVE_CONNECTOR_CERTIFICATION_PREPARATION.md unchanged.
Neither AWS_LIVE_CERTIFIED nor AZURE_LIVE_CERTIFIED has been achieved.

## Browser execution attempt

The in-app browser bootstrap failed before browser access with:

```text
Mcp error: -32602: js: codex/sandbox-state-meta: missing field `sandboxPolicy`
```

Classification: browser tool configuration blocker. No page was opened and no
integrated product journey was executed. This failure is not evidence of a
Nexora product defect. Restore the browser tool's sandbox configuration before
resuming this gate; no Nexora code change is indicated by this error.

## Bounded UAT scope on resumption

The operator subsequently supplied manual Ask Nexora UAT evidence: rendering,
read-only behavior, and unsupported forecast rejection passed; financial and
service-risk retrieval required a correction. This supersedes the earlier
tooling-only status. See `ASK_NEXORA_UAT_DEFECT.md` for the scoped correction,
validation, and three-case operator re-test. The assistant browser-tool failure
above remains historical evidence; no automated browser pass is claimed.

Use only an isolated local runtime with synthetic/non-confidential evidence.
Confirm that runtime's data source before interacting with it.

1. Validate login, role-specific navigation, and access boundaries.
2. Follow the supported evidence intake and review journey into product views.
3. Check executive summaries, financial views, evidence lineage, and empty states.
4. Exercise supported governance/approval and report/export journeys locally.
5. Check persistence across reload and capture screenshots and observed outcomes.
6. Record actual defects separately from unavailable external integrations and
   obtain operator acceptance of the demonstrated product journey.

Do not reopen connector preparation or run another architecture assessment.
Presentation readiness remains unverified until this journey is observed;
final release remains pending with external deployment certifications explicit.

This attempt changed release documentation only. No cloud credentials were
configured, no cloud certification calls were made, and no commit or push occurred.
