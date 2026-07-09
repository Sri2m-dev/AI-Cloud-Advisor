# Repository Self-Containment Audit

Date: 2026-07-09  
Repository Audited: `AI-Cloud-Advisor-recovery-ui`  
Branch: `feature/e8-universal-connector-framework`  
Known HEAD: `aed845928 Add E8.1 release review documentation`  
Scope: Verification only  
Code Changes: None

## Executive Summary

`AI-Cloud-Advisor-recovery-ui` is the correct canonical codebase candidate, but the audit identifies several release-hygiene gaps that should be resolved before the repository is promoted and tagged as the long-lived source of truth.

Overall recommendation:

```text
Repository promotion: CONDITIONALLY READY
Release tagging: NOT YET
Required before tag: resolve documentation and secret-hygiene gaps, then run E8.1.17
```

The active Python surface is internally coherent from a syntax perspective, and the core connector framework packages import successfully. The main gaps are repository packaging and fresh-clone operability:

- No root `README.md`.
- No root `.env.example`.
- `.streamlit/credential.key` is tracked.
- Optional connector/runtime dependencies are referenced by active files but are not clearly represented in the primary dependency set.
- Startup is documented, but a full fresh-clone startup validation was not executed during this audit.

These are fixable release-readiness issues, not reasons to return to the old `AI-Cloud-Advisor` workspace.

## Audit Method

The audit checked:

- Repository status and branch.
- Python file inventory.
- Active Python syntax validity without writing bytecode.
- Core package import smoke checks.
- Dependency files.
- Environment templates.
- Startup documentation.
- Hardcoded local path references.
- Git tracking for sensitive runtime files.

No production code was modified. No repository rename, merge, push, commit, tag, or E8.2 work was performed.

## Repository State

Observed state:

```text
Branch:
feature/e8-universal-connector-framework

HEAD:
aed845928 Add E8.1 release review documentation
```

Current untracked documentation artifacts:

```text
docs/GITHUB_CUTOVER_RUNBOOK.md
docs/REPOSITORY_CONSOLIDATION_ASSESSMENT.md
docs/SOURCE_OF_TRUTH_CUTOVER_PLAN.md
```

This audit document is also documentation-only and should remain uncommitted until reviewed.

## 1. Required Python Modules

### Result

```text
Status: PASS with release-surface caveat
```

A read-only syntax scan was run across the active Python surface, excluding `.git`, `.venv`, `__pycache__`, `archive`, `backup_unused`, and `.streamlit`.

Observed result:

```text
Active Python files scanned: 936
Syntax errors: 0
```

Core connector/platform package import smoke check:

```text
connector_sdk                         PASS
connector_registry                    PASS
connector_runtime                     PASS
connector_auth                        PASS
connector_normalization               PASS
connector_persistence                 PASS
connector_orchestration               PASS
connector_observability               PASS
connector_migration                   PASS
connector_adapters                    PASS
connectors.aws                        PASS
connectors.gcp                        PASS
services.enterprise_financial_model   PASS
services.platform.business_context_service PASS
```

`app_main` failed under direct bare Python import with `NoSessionContext`. This is expected for a Streamlit entrypoint that expects execution through `streamlit run`; it is not evidence of a missing module.

### Caveat

The repository still contains large historical directories such as `archive/` and `backup_unused/`. These were intentionally excluded from the active release-surface scan because they are not part of the canonical runtime baseline.

Recommendation:

```text
Before long-term promotion, decide whether archive/backup_unused should remain in the canonical repository, move to an external archive, or be excluded from release packaging.
```

## 2. Dependency Files

### Result

```text
Status: PARTIAL
```

Present dependency/configuration files:

```text
requirements.txt
requirements-dev.txt
requirements-prod.txt
requirements.frontend.txt
pyproject.toml
runtime.txt
```

The primary `requirements.txt` includes the main Streamlit/Supabase/data stack.

Potential dependency gaps were found in active files that reference optional runtime/provider libraries:

```text
boto3
azure.identity
azure.mgmt.costmanagement
azure.mgmt.resource
azure.core
redis
celery
prometheus_client
```

Some of these may be intentionally optional, but the repository should make that explicit before promotion.

Recommended follow-up:

```text
Add or document optional dependency groups for:
- cloud provider live connectors
- backend/API services
- observability
- worker/scheduler runtime
```

This can be handled without changing production logic.

## 3. Environment Templates

### Result

```text
Status: PARTIAL
```

Found:

```text
.streamlit/secrets.toml.example
docs/NEXORA_ENVIRONMENT_CONFIGURATION.md
```

Missing:

```text
.env.example
```

The environment configuration documentation defines the required variables:

```text
SUPABASE_URL
SUPABASE_KEY
DEFAULT_ORG_ID
ENVIRONMENT
OPENAI_API_KEY conditional
```

The Streamlit secrets template includes:

```text
PGDATABASE
PGUSER
PGPASSWORD
PGHOST
PGPORT
CLOUD_ADVISOR_CREDENTIAL_KEY
CLOUD_ADVISOR_APP_URL
STRIPE_SECRET_KEY
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_KEY
YAGMAIL_USER
YAGMAIL_PASSWORD
FEEDBACK_REPORT_EMAIL_TO
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_DEFAULT_REGION
```

Recommendation:

```text
Create a root .env.example or clearly designate .streamlit/secrets.toml.example as the only supported local template.
```

## 4. Secret Hygiene

### Result

```text
Status: NEEDS ATTENTION
```

Git tracking check found:

```text
.streamlit/credential.key is tracked
.streamlit/secrets.toml.example is tracked
pyproject.toml is tracked
requirements-dev.txt is tracked
requirements-prod.txt is tracked
requirements.frontend.txt is tracked
```

Root `.env` is present in the file tree but not tracked by Git.

`.gitignore` excludes:

```text
.env
.env.*
.streamlit/secrets.toml
```

Concern:

```text
.streamlit/credential.key should be reviewed before repository promotion.
```

If it is a real credential, it should not remain tracked. If it is a harmless placeholder, it should be renamed or documented as an example/template file.

Recommendation before release tag:

```text
Verify .streamlit/credential.key content and decide whether to remove it from tracking or replace it with a non-secret template.
```

## 5. README and Architecture Documentation

### Result

```text
Status: PARTIAL
```

No root `README.md` was found.

Strong documentation exists under `docs/`, including:

```text
docs/NEXORA_DEPLOYMENT_GUIDE.md
docs/NEXORA_ENVIRONMENT_CONFIGURATION.md
docs/NEXORA_PLATFORM_ARCHITECTURE.md
docs/E8_UNIVERSAL_CONNECTOR_FRAMEWORK.md
docs/ARCHITECTURE_DECISION_INDEX.md
docs/NEXORA_RELEASE_NOTES_v1.1.0.md
docs/NEXORA_v1.1.0_FEATURE_MATRIX.md
```

However, a fresh clone should have a root-level entry document that answers:

- What is Nexora?
- What is the canonical entrypoint?
- How do I install dependencies?
- How do I configure environment variables?
- How do I start the app?
- Which docs should I read first?
- What is the current release status?

Recommendation:

```text
Add a root README.md before or during repository promotion.
```

## 6. Old Repository Path References

### Result

```text
Status: PASS for active code, PARTIAL for archived docs
```

No active Python imports were found that reference:

```text
AI-Cloud-Advisor-recovery-ui
AI_Cloud_Advisor
from AI-Cloud-Advisor
import AI-Cloud-Advisor
```

Hardcoded local path references appear primarily in:

```text
backup_unused/
archive/AI-CLOUD-ADVISOR_BACKUP/
docs/REPOSITORY_CONSOLIDATION_ASSESSMENT.md
docs/SOURCE_OF_TRUTH_CUTOVER_PLAN.md
docs/GITHUB_CUTOVER_RUNBOOK.md
```

The documentation references are intentional because they describe the cutover.

Active-code note:

```text
services/db.py references database name "AI-Cloud-Advisor-Dev".
```

This is a database identifier, not a local path. It should be reviewed during future product renaming, but it does not block repository promotion.

## 7. Broken Relative Imports

### Result

```text
Status: PASS for core release packages
```

The active syntax scan found no parse errors.

Core packages imported successfully:

```text
connector_sdk
connector_registry
connector_runtime
connector_auth
connector_normalization
connector_persistence
connector_orchestration
connector_observability
connector_migration
connector_adapters
connectors.aws
connectors.gcp
```

No old-repository import paths were detected.

Caveat:

```text
This was not a complete runtime import of all 936 active Python files. Some optional modules depend on provider/runtime libraries that may not be installed in the base environment.
```

The full release validation remains E8.1.17.

## 8. Startup Commands

### Result

```text
Status: DOCUMENTED, NOT FULLY EXECUTED IN THIS AUDIT
```

Startup commands are documented in `docs/NEXORA_DEPLOYMENT_GUIDE.md`:

```powershell
python -m streamlit run app_main.py
python -m streamlit run app_main.py --server.port 8513
```

The direct `app_main` import under bare Python produced a Streamlit context failure, which is expected when not launched through Streamlit.

This audit did not start a fresh Streamlit server or perform route checks. That should remain part of the post-cutover E8.1.17 validation.

Recommendation:

```text
After cutover, validate startup from canonical main using the documented Streamlit command and route smoke checks.
```

## 9. Fresh Clone Readiness

### Result

```text
Status: CONDITIONALLY READY
```

The repository appears structurally capable of serving as a fresh-clone baseline, provided the following are addressed:

1. Add a root `README.md`.
2. Add or explicitly replace root `.env.example` with documented `.streamlit/secrets.toml.example` usage.
3. Review tracked `.streamlit/credential.key`.
4. Document optional provider/backend dependencies.
5. Decide whether archive/backup directories remain in the canonical release repository.
6. Run E8.1.17 after GitHub cutover.

## Risks

| Risk | Severity | Finding | Recommendation |
| --- | --- | --- | --- |
| Missing root README | Medium | Fresh clone lacks first-stop guidance | Add root `README.md` |
| Missing root `.env.example` | Medium | Environment setup may be unclear | Add `.env.example` or explicitly standardize on Streamlit secrets template |
| Tracked credential key | High | `.streamlit/credential.key` is tracked | Verify/remove/replace with template before public or production release |
| Optional dependency ambiguity | Medium | Active files reference provider/backend libs not clearly in main requirements | Document or add optional dependency groups |
| Archive folders in canonical repo | Medium | Historical code may confuse future scans/reviews | Move/archive externally or mark as non-release surface |
| Startup not fully revalidated here | Medium | Startup command documented but not run from clean clone | Execute during E8.1.17 |

## Technical Debt

Release-hygiene debt identified:

- Root onboarding documentation is missing.
- Environment template strategy is split between docs and `.streamlit/secrets.toml.example`.
- Optional dependency strategy needs clarification.
- Historical archive folders remain inside the repository.
- Product naming still mixes Nexora and AI-Cloud-Advisor in places.
- Database identifier `AI-Cloud-Advisor-Dev` remains in active service code.

These do not invalidate the recovery repository as canonical, but they should be addressed as part of cutover hardening.

## Final Recommendation

The recovery repository should still become the canonical source of truth.

Recommended next sequence:

```text
1. Review this self-containment audit.
2. Resolve or explicitly accept the release-hygiene gaps.
3. Commit the repository governance/cutover docs if approved.
4. Perform GitHub cutover from the recovery baseline.
5. Run E8.1.17 on canonical main.
6. Tag v1.1.0-universal-connectors only if E8.1.17 is GO.
```

Go / No-Go:

```text
Repository promotion: GO, with conditions
Immediate release tag: NO-GO until post-cutover E8.1.17 and secret/documentation checks pass
Return to old AI-Cloud-Advisor workspace: NO-GO
```
