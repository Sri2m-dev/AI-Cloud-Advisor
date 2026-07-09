# GitHub Cutover Runbook

Date: 2026-07-09  
Input: `docs/SOURCE_OF_TRUTH_CUTOVER_PLAN.md`  
Scope: Git repository cutover planning only  
Code Changes: None

## Executive Summary

The recovery repository is now the canonical Nexora codebase:

```text
Canonical working codebase:
AI-Cloud-Advisor-recovery-ui

Canonical product / repository name:
AI-Cloud-Advisor
```

The objective of this runbook is to promote the clean recovery baseline to the official GitHub repository identity without merging it into the dirty original local workspace.

The release sequence should become:

```text
Repository Decision
    -> GitHub Cutover
    -> PR / Baseline Review
    -> E8.1.17 Release Validation
    -> v1.1.0-universal-connectors Tag
    -> Program P3
```

No release tag should be created until the cutover is complete and E8.1.17 passes on the canonical repository.

## 1. Current Repository Topology

Current local topology:

```text
C:\Users\SrikanthMudaliar\AI-Cloud-Advisor
    Original local workspace
    Dirty / divergent / historical
    Not recommended as the merge target

C:\Users\SrikanthMudaliar\AI-Cloud-Advisor-recovery-ui
    Recovery workspace
    Clean release candidate
    Recommended source of truth
```

Current product identity:

```text
Product:
Nexora / AI-Cloud-Advisor

Preferred GitHub repository name:
AI-Cloud-Advisor
```

Current recovery release candidate:

```text
Branch:
feature/e8-universal-connector-framework

Known release documentation HEAD:
aed845928 Add E8.1 release review documentation
```

## 2. Recommended Canonical Repository

Recommended decision:

```text
Promote AI-Cloud-Advisor-recovery-ui as the canonical codebase.
Keep AI-Cloud-Advisor as the official product/repository name.
```

The recovery workspace should be treated as:

- The clean product baseline.
- The v1.1.0 release candidate.
- The future development source of truth.
- The source for GitHub cutover.

The original local `AI-Cloud-Advisor` workspace should be treated as:

- Historical.
- Archival.
- Useful for reference only.
- Not suitable for direct merge into the release baseline.

## 3. Backup Procedure

Before any GitHub cutover, preserve the original repository state.

### 3.1 Backup Remote Main

From a clean clone or through GitHub:

1. Capture the current `main` SHA.
2. Create an archive branch:

```text
archive/pre-recovery-main
```

3. Optionally create a pre-cutover tag:

```text
pre-v1.1.0-original-main
```

4. Confirm both are visible on GitHub.

### 3.2 Backup Local Original Workspace

Preserve the old local workspace before renaming anything:

```text
AI-Cloud-Advisor
    -> AI-Cloud-Advisor-backup-YYYYMMDD
```

The backup should preserve:

- Local-only source files.
- Local databases.
- SQL backups.
- Historical scripts.
- Presentations and reports.
- Demo artifacts.
- Non-secret local configuration.

Secrets should remain outside Git and should not be copied into any repository commit.

### 3.3 Original-Only Asset Inventory

Before archival, produce or maintain an inventory of original-only assets that may have business value:

- SQL exports.
- Legacy reports.
- Historical generated screenshots.
- Local runbooks.
- Presentation decks.
- Customer-specific examples.
- One-off scripts.

These should be archived separately from the canonical release repository.

## 4. Local Rename Procedure

Only perform local renames after remote backup is complete.

Recommended local rename flow:

```text
AI-Cloud-Advisor
    -> AI-Cloud-Advisor-backup-YYYYMMDD

AI-Cloud-Advisor-recovery-ui
    -> AI-Cloud-Advisor
```

After rename:

1. Open the renamed `AI-Cloud-Advisor` folder.
2. Verify Git status:

```powershell
git status --short
git branch --show-current
git log -1 --oneline
```

3. Confirm the repo is the recovery Git history, not the old local workspace.
4. Confirm the release candidate branch and documents are still present.

If there is any uncertainty, stop and do not push.

## 5. Remote Rename Procedure

There are two safe remote approaches.

### Approach A: Keep Existing GitHub Repository Name

Use the existing GitHub `AI-Cloud-Advisor` repository as the official destination.

Process:

1. Back up current remote `main`.
2. Confirm the recovery repo remote points to the intended GitHub repository.
3. Push the recovery release branch.
4. Open a PR into `main`.
5. Treat the PR as a baseline cutover.
6. Merge only after backup and review.

This is the recommended approach because it keeps product continuity.

### Approach B: Rename GitHub Repository

Rename the GitHub repository itself, if the organization decides to adopt a new brand such as `Nexora`.

Process:

1. Back up current `AI-Cloud-Advisor`.
2. Rename the GitHub repository through GitHub settings.
3. Update local remotes.
4. Push the recovery baseline.
5. Validate all branch protections and actions.

This should only be done if the product owner approves the brand-level repository rename.

## 6. Git Remote Verification

Before pushing anything, verify:

```powershell
git remote -v
git branch --show-current
git log -1 --oneline
git status --short
```

Expected checks:

- `origin` points to the intended GitHub repository.
- Current branch is the recovery release candidate branch or canonical `main` after cutover.
- HEAD matches the expected release candidate commit.
- Worktree is clean except approved documentation-only files.

Do not push if:

- The remote points to the wrong repository.
- The current folder is the old original workspace.
- The worktree contains unreviewed code changes.
- Secrets or local artifacts are staged.

## 7. Branch Migration

Recommended branches:

```text
main
    Official canonical branch after cutover

feature/e8-universal-connector-framework
    P2 release candidate branch

archive/pre-recovery-main
    Backup of old official main
```

Branch migration steps:

1. Preserve old `main` as `archive/pre-recovery-main`.
2. Push recovery release candidate branch if not already pushed.
3. Open PR:

```text
feature/e8-universal-connector-framework -> main
```

4. Label the PR as:

```text
baseline-cutover
release-candidate
p2-universal-connectors
```

5. Review the PR for release scope, not line-by-line recovery history.
6. Merge only after backup confirmation.

## 8. Tag Migration

Existing historical tags should be preserved.

The v1.1.0 tag must be created only after:

1. GitHub cutover is complete.
2. `main` contains the recovery baseline.
3. E8.1.17 passes.
4. Product owner approves release.

Release tag:

```text
v1.1.0-universal-connectors
```

Do not create this tag on:

- The old local original workspace.
- The pre-cutover GitHub `main`.
- A feature branch before merge.
- A repository with unvalidated cutover state.

## 9. Release Migration

The release should migrate with the recovery baseline, not with the old workspace.

Release order:

```text
1. Backup old GitHub main.
2. Promote recovery baseline.
3. Merge cutover PR into main.
4. Pull canonical main locally.
5. Run E8.1.17.
6. Review validation report.
7. Tag v1.1.0-universal-connectors only if GO.
8. Push tag.
9. Mark Program P2 complete.
```

Release artifacts expected after validation:

```text
docs/E8_1_17_RELEASE_VALIDATION.md
docs/E8_1_RELEASE_REVIEW.md
docs/NEXORA_v1.1.0_FEATURE_MATRIX.md
docs/ARCHITECTURE_DECISION_INDEX.md
```

## 10. GitHub Settings to Verify

Before and after cutover, verify these GitHub settings:

- Default branch is `main`.
- Branch protection is enabled for `main`.
- Required reviews are configured as expected.
- Required checks are configured as expected.
- Secret scanning is enabled if available.
- Push protection is enabled if available.
- Dependabot/security alerts are enabled if available.
- Repository visibility is correct.
- Team permissions are correct.
- Actions/workflows are enabled only if expected.
- Environments and secrets are still valid.
- Remote URL in local clone matches the official repository.

Also verify repository metadata:

- Description.
- Topics.
- README.
- License.
- Default branch.
- Release notes location.

## 11. Validation After Cutover

After the cutover merge, execute E8.1.17 from canonical `main`.

### Repository Validation

```powershell
git checkout main
git pull origin main
git status --short
git log -1 --oneline
```

Expected:

- On `main`.
- Latest merge contains recovery baseline.
- Worktree clean.
- No generated artifacts, secrets, caches, or local runtime files are tracked unexpectedly.

### Compile Validation

Compile connector framework packages:

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
connectors/aws
connectors/gcp
```

### Runtime Validation

Validate:

- AWS discovery-only.
- AWS dry-run.
- Azure discovery-only.
- Azure dry-run.
- GCP discovery-only.
- GCP dry-run.

### Security Validation

Confirm:

- `FULL_SYNC` disabled by default.
- Azure runtime metadata contains no `client_secret`.
- Azure uses `secret_ref`.
- Dry-run publishes zero records.
- Secrets are not committed.

### Platform Regression

Validate:

- Executive Workspace.
- CIO Workspace.
- Business Architecture.
- Existing AWS production sync path.
- Connector registry.
- Approval/action paths remain uncached.

## 12. Rollback Procedure

### If Cutover Fails Before Merge

1. Do not merge PR.
2. Keep old `main` unchanged.
3. Fix recovery branch or update runbook.
4. Re-review.

### If Cutover Fails After Merge But Before Tag

1. Do not create `v1.1.0-universal-connectors`.
2. Revert the merge commit or restore from:

```text
archive/pre-recovery-main
```

3. Keep recovery branch intact.
4. Resolve issues on a new cutover branch.
5. Re-run validation.

### If Validation Fails

1. Do not tag.
2. Record the failure in the release validation report.
3. Decide whether to fix forward or rollback.
4. If fixing forward, keep all changes scoped and rerun E8.1.17.
5. If rolling back, restore from archive branch.

### If Tag Is Created Prematurely

1. Stop the release.
2. Do not announce.
3. Get explicit product-owner approval before deleting any remote tag.
4. Delete and recreate the tag only after validation passes.

## 13. Checklist

### Pre-Cutover

- [ ] Freeze old `AI-Cloud-Advisor` workspace.
- [ ] Confirm recovery is canonical source of truth.
- [ ] Confirm no E8.2 work has started.
- [ ] Back up current GitHub `main`.
- [ ] Create `archive/pre-recovery-main`.
- [ ] Optionally create `pre-v1.1.0-original-main`.
- [ ] Archive local original workspace.
- [ ] Inventory original-only assets.
- [ ] Confirm recovery branch HEAD.
- [ ] Confirm recovery worktree clean.

### GitHub Cutover

- [ ] Verify remote URL.
- [ ] Push recovery release branch if needed.
- [ ] Open PR into `main`.
- [ ] Mark PR as baseline cutover.
- [ ] Confirm no merge conflicts.
- [ ] Confirm branch protection expectations.
- [ ] Merge only after backup confirmation.

### Post-Cutover

- [ ] Checkout canonical `main`.
- [ ] Pull latest.
- [ ] Confirm clean worktree.
- [ ] Run E8.1.17.
- [ ] Generate `docs/E8_1_17_RELEASE_VALIDATION.md`.
- [ ] Review GO / NO-GO.
- [ ] Tag only if GO.
- [ ] Push `v1.1.0-universal-connectors`.
- [ ] Mark P2 complete.

### Blocked Until Release Tag

- [ ] Do not start P3 / E8.2.
- [ ] Do not add connector enhancements.
- [ ] Do not modify dashboards.
- [ ] Do not change schemas.
- [ ] Do not alter runtime architecture.

## Final Recommendation

Proceed with a controlled GitHub cutover using recovery as the source of truth:

```text
1. Archive old AI-Cloud-Advisor.
2. Promote AI-Cloud-Advisor-recovery-ui.
3. Keep AI-Cloud-Advisor as the official GitHub/product name.
4. Merge the recovery baseline only after backup.
5. Run E8.1.17 on canonical main.
6. Tag v1.1.0-universal-connectors only after GO.
```

The old workspace should remain a historical backup, not an active merge target.
