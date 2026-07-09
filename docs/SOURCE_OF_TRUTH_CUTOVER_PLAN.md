# Source-of-Truth Cutover Plan

Date: 2026-07-09  
Input: `docs/REPOSITORY_CONSOLIDATION_ASSESSMENT.md`  
Scope: Repository source-of-truth decision and safe cutover plan  
Code Changes: None

## Executive Summary

Nexora should treat the recovery codebase as the canonical working product baseline:

```text
Canonical working codebase:
AI-Cloud-Advisor-recovery-ui

Canonical product / repository name:
AI-Cloud-Advisor
```

The current local `AI-Cloud-Advisor` workspace should not receive a direct file merge from recovery. It is dirty, noisy, and structurally divergent. The safe path is to promote the clean recovery baseline and align it to the official product repository/name through a controlled cutover.

## 1. Final Recommended Canonical Repository

Recommended decision:

```text
AI-Cloud-Advisor-recovery-ui becomes the canonical codebase.
AI-Cloud-Advisor remains the canonical product/repository name after cutover.
```

This separates two concerns:

- Codebase quality and release readiness: recovery wins.
- Product continuity and GitHub naming: `AI-Cloud-Advisor` can remain the official name.

## 2. Why Recovery Should Become the Release Baseline

`AI-Cloud-Advisor-recovery-ui` should become the release baseline because it contains the current Nexora platform architecture:

- Stabilized Executive Workspace.
- Stabilized CIO Workspace.
- Business Architecture domain.
- Shared Platform Framework.
- Enterprise Financial Model integration.
- Knowledge Graph and Digital Twin work.
- Universal Connector Framework.
- Connector runtime, registry, auth, normalization, persistence, orchestration, and observability.
- AWS, Azure, and GCP runtime adapter seams.
- ADR governance.
- Release review documentation.
- v1.1.0 feature matrix.
- Clean worktree on the release candidate branch.

It also has the correct application structure:

```text
Thin app_main.py
    -> role-based routing
    -> modular pages
    -> services
    -> repositories
    -> platform frameworks
```

This is the architecture that supports Nexora as an Enterprise Intelligence Platform.

## 3. Why the Original Workspace Should Not Be Directly Merged

The local original workspace `AI-Cloud-Advisor` should not be directly merged because it contains:

- Dirty tracked `.venv` and package artifacts.
- Generated `__pycache__` and `.pyc` noise.
- Local logs.
- Local database changes.
- Historical backup folders mixed into the active workspace.
- Partial recovery-era files.
- A monolithic `app_main.py`.
- Divergent configuration and dependency files.
- Many files with the same path but different architecture.

Directly merging recovery into this workspace would create risks:

- Duplicate abstractions.
- Conflicting entrypoints.
- Conflicting connector frameworks.
- Regression risk across dashboards.
- Unclear Git history.
- Difficult release validation.
- Future confusion about which codebase is authoritative.

Conclusion:

```text
Do not merge recovery into the dirty local original folder.
Promote recovery as the clean baseline instead.
```

## 4. Cutover Options

### Option A: Rename / Promote Recovery Repository

Promote `AI-Cloud-Advisor-recovery-ui` as the canonical local and remote repository.

Possible steps:

1. Rename local folder from `AI-Cloud-Advisor-recovery-ui` to `AI-Cloud-Advisor`.
2. Archive the old local `AI-Cloud-Advisor` folder.
3. Update remote origin if needed.
4. Continue release validation from the promoted recovery repo.

Pros:

- Cleanest local developer experience.
- Avoids merging into a dirty workspace.
- Preserves recovery Git state and release branch.

Cons:

- Requires careful local folder/remote coordination.
- May require updating IDE paths, scripts, and documentation references.

### Option B: Push Recovery Baseline to Existing GitHub `AI-Cloud-Advisor` After Backup

Use recovery as the source, but keep the official GitHub repository name.

Possible steps:

1. Back up the current GitHub `main`.
2. Preserve the original repo history through a tag or archival branch.
3. Merge or replace GitHub `main` with the recovery release baseline.
4. Run E8.1.17 from the merged `main`.
5. Tag `v1.1.0-universal-connectors` after validation.

Pros:

- Keeps official product/repo name.
- Promotes the clean codebase.
- Avoids direct local dirty merge.
- Best fit for commercial product continuity.

Cons:

- Must be handled carefully to preserve old history.
- Reviewers must understand this is a baseline cutover, not a normal feature diff.

### Option C: Keep Both Temporarily

Keep:

```text
AI-Cloud-Advisor              -> original / archive / legacy reference
AI-Cloud-Advisor-recovery-ui  -> active development and release baseline
```

Pros:

- Lowest immediate disruption.
- Original remains available for legacy reference.
- No risky overwrite.

Cons:

- Long-term confusion.
- Two repo names continue to exist.
- Future contributors may target the wrong repo.
- Release/tag story remains muddy.

## 5. Recommended Option

Recommended option:

```text
Option B:
Push recovery baseline to the existing GitHub AI-Cloud-Advisor repository after backup.
```

Rationale:

- The product should keep the `AI-Cloud-Advisor` GitHub identity.
- The recovery codebase should become the source of truth.
- The dirty local original workspace should not be used as the merge target.
- Official releases should be tagged from the clean canonical baseline.

## 6. Step-by-Step Safe Cutover Process

### Phase 1: Freeze

1. Freeze the current recovery release candidate.
2. Do not add new code.
3. Do not start P3 / E8.2.
4. Do not tag v1.1.0 yet.

### Phase 2: Backup Existing Official Repository State

From a clean clone or GitHub UI:

1. Confirm current remote `main` SHA.
2. Create a backup branch:

```text
archive/pre-recovery-main
```

3. Optionally create a pre-cutover tag:

```text
pre-v1.1.0-original-main
```

4. Export or preserve any original-only release assets if required.

### Phase 3: Promote Recovery Baseline

Use recovery as the source baseline:

1. Confirm recovery branch:

```text
feature/e8-universal-connector-framework
```

2. Confirm HEAD:

```text
aed845928 Add E8.1 release review documentation
```

3. Confirm worktree clean.
4. Open/retain PR from recovery branch into official `main`.
5. Ensure PR review treats this as a baseline cutover.
6. Merge only after review and backup are complete.

### Phase 4: Post-Merge Validation

After merge:

1. Run E8.1.17 Post-Merge Release Gate.
2. Generate:

```text
docs/E8_1_17_RELEASE_VALIDATION.md
```

3. Review GO / NO-GO recommendation.

### Phase 5: Release Tag

Only if E8.1.17 is GO:

```text
v1.1.0-universal-connectors
```

Do not tag before validation.

## 7. Backup Steps

Minimum backup requirements:

- Preserve remote `main` before cutover.
- Preserve local original workspace separately.
- Preserve original-only non-source artifacts that might have business value.
- Preserve database backups outside the Git release path.
- Preserve `.env*` files outside Git.

Recommended backup artifacts:

```text
archive/pre-recovery-main branch
pre-v1.1.0-original-main tag
local folder backup of AI-Cloud-Advisor
exported original-only assets list
```

Original-only assets to review before archival:

- Presentation decks.
- SQL backups.
- Legacy sync scripts.
- Historical cost reports.
- Demo artifacts.
- Any customer-specific local files.

## 8. Validation Steps After Cutover

After recovery is merged into canonical `main`:

### Repository Validation

- `git checkout main`
- `git pull origin main`
- `git status --short`
- Confirm no unexpected dirty files.
- Confirm `.venv`, caches, logs, and secrets are not part of the release surface.

### Compile Validation

Compile:

- Connector framework packages.
- Executive Workspace pages.
- CIO Workspace pages.
- Business Architecture pages.
- Shared platform framework.

### Runtime Validation

Run:

- AWS discovery-only.
- AWS dry-run.
- Azure discovery-only.
- Azure dry-run.
- GCP discovery-only.
- GCP dry-run.

Confirm:

- `FULL_SYNC` disabled by default.
- Azure runtime metadata contains no `client_secret`.
- Azure uses `secret_ref`.
- Dry-run publishes zero records.

### Platform Regression

Validate:

- Executive Workspace.
- CIO Workspace.
- Business Architecture.
- Authentication.
- Connector registry.
- Existing AWS production path.
- Approval/action paths remain uncached.

## 9. GitHub Sync Steps

Recommended GitHub workflow:

1. Confirm PR branch:

```text
feature/e8-universal-connector-framework
```

2. Confirm PR target:

```text
main
```

3. Confirm latest branch commit:

```text
aed845928 Add E8.1 release review documentation
```

4. Confirm backup branch/tag exists for current `main`.
5. Review PR as a baseline cutover.
6. Merge PR.
7. Pull merged `main` locally.
8. Run E8.1.17.
9. If validation passes, create and push:

```text
v1.1.0-universal-connectors
```

10. Mark P2 complete.

## 10. Risks and Rollback Plan

### Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| GitHub `main` loses original history context | Medium | Create backup branch/tag before cutover. |
| Original-only useful assets are missed | Medium | Inventory and archive original-only artifacts before archival. |
| PR appears too large for normal review | High | Label it explicitly as a baseline cutover. |
| Local original workspace remains confusing | Medium | Rename/archive it after cutover. |
| Release validation fails after cutover | Medium | Do not tag; fix on canonical baseline branch. |
| Secrets or local artifacts leak into canonical baseline | High | Verify `.gitignore`, status, and release surface before merge/tag. |

### Rollback Plan

If cutover fails before tag:

1. Do not create `v1.1.0-universal-connectors`.
2. Revert the merge commit or reset remote `main` through a protected rollback process.
3. Restore from:

```text
archive/pre-recovery-main
```

4. Keep recovery branch intact.
5. Resolve issues in a new cutover branch.

If cutover succeeds but validation fails:

1. Do not tag.
2. Keep merged `main` as the canonical baseline only if issues are fixable quickly.
3. Otherwise rollback to pre-cutover branch.
4. Re-run validation after fixes.

If tag is accidentally created before validation:

1. Stop release.
2. Do not announce release.
3. Delete local and remote tag only with explicit product-owner approval.
4. Re-run E8.1.17.
5. Recreate tag only after GO.

## Final Recommendation

Proceed with a controlled source-of-truth cutover:

```text
1. Treat AI-Cloud-Advisor-recovery-ui as canonical codebase.
2. Preserve AI-Cloud-Advisor as canonical product/repo name.
3. Back up current GitHub main.
4. Merge recovery baseline into official main as a baseline cutover.
5. Run E8.1.17.
6. Tag v1.1.0-universal-connectors only after validation passes.
```

Do not merge recovery into the dirty local original workspace. The release should be validated and tagged from the clean canonical recovery baseline after it has been promoted to the official repository.
