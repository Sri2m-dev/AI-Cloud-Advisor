# v1.2.0 Data Fabric Merge Preparation

## Status

Prepared only. **No merge or tag has been executed or authorized by this document.**

## Merge coordinates

- Source branch: `feature/p3-supabase-live-validation`
- Target branch: `main`
- Hosted-tested engineering commit: `5ff2e57195861b7cb1fcbac3f7804ce15db8768d`
- Hosted CI run: `29671495028` — success
- Final candidate: the remote source-branch head after this Phase 5 documentation package is committed; verify it with `git rev-parse` and `git ls-remote` during approval.
- Proposed tag: `v1.2.0-data-fabric`

## Required pre-merge review

1. Confirm the source worktree is clean and synchronized.
2. Review the complete `main...feature/p3-supabase-live-validation` diff.
3. Review `REPOSITORY_CERTIFICATION.md`, `v1.2.0_RELEASE_READINESS.md`, `TECHNICAL_DEBT_REGISTER.md`, and `HOSTED_CI_CERTIFICATION.md`.
4. Confirm relationship-version history remains accepted deferred scope.
5. Confirm the Phase 5 documentation-only descendant contains no runtime or Data Fabric change after hosted-tested commit `5ff2e571...`.
6. Obtain explicit merge authorization.

## Merge strategy

Recommended: non-fast-forward merge to preserve the reviewed release-candidate boundary.

Prepared commands, not executed:

```text
git checkout main
git pull --ff-only origin main
git merge --no-ff feature/p3-supabase-live-validation
git status --short --branch
```

Resolve no conflict by silently choosing one side. If conflicts occur, stop, record affected files, and repeat relevant certification after resolution.

## Rollback strategy

Before tagging, prefer correction or revert of the untagged merge commit. After a published merge, use a new revert commit rather than rewriting `main` history:

```text
git revert -m 1 <merge-commit>
git push origin main
```

Database rollback is not part of this source merge. Migrations 0001–0018 were already applied and must not be automatically reversed or reapplied. Any database rollback requires a separately reviewed operational plan.

## Post-merge validation checklist

- [ ] Capture the merge commit hash.
- [ ] Confirm `main` is clean and synchronized with origin.
- [ ] Confirm hosted CI runs on the merge commit and succeeds.
- [ ] Confirm 325 tests collect.
- [ ] Confirm 320 pass, five expected integrations skip, and zero fail.
- [ ] Confirm the 94-test P3 gate passes.
- [ ] Confirm five integrations collect and skip without secrets.
- [ ] Confirm active compile/import and Ruff gates pass.
- [ ] Confirm no live Supabase validation ran as part of ordinary CI.
- [ ] Review CD behavior before allowing image publication or deployment.
- [ ] Obtain explicit tag authorization.

## Post-release smoke tests

After an authorized deployment:

- Verify the application starts through `app_main.py`.
- Verify authentication and representative Executive/CIO routes load.
- Verify approval-service SLA and RBAC focused tests remain green.
- Verify connector and scheduled-job health without exposing credentials.
- Verify Data Fabric health/read paths only through approved operational checks.
- Do not rerun live P3 mutation scenarios against production.

## Tag preparation

Tag only the reviewed merge commit after hosted post-merge CI and explicit authorization:

```text
git tag -a v1.2.0-data-fabric <merge-commit> -m "P3 Data Fabric Foundation"
git push origin v1.2.0-data-fabric
```

The tag commands are documentation only and must not be run during Phase 5.

