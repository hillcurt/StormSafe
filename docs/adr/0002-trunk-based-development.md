# ADR 0002 — Trunk-based development

**Status:** accepted
**Date:** 2026-10-17

## Context
StormSafe has one human developer and coding agents producing most of the code. Agents work fastest on small, well-scoped changes, and a safety system needs every change reviewed. Long-lived branches would let agent work drift from `trunk` and make reviews large and risky.

## Decision
Use trunk-based development with short-lived branches:
- The only long-lived branch is named `trunk` (also the repo default branch) and is always releasable.
- Branches come off the latest `trunk` and merge within a day, through a PR with passing CI and human approval.
- Unfinished behavior merges behind a config flag that defaults to off.
- Deploys come from tagged commits on `trunk`.

## Consequences
- Specs must be sliced into PRs small enough to review in one sitting.
- Feature flags become part of the config contract and need cleanup once a feature is complete.
- CI on `trunk` must stay fast and reliable, because a red trunk blocks everything.

## Alternatives considered
- **GitFlow** (`develop` + `release/*`): adds merge overhead with no benefit for a single deployable service.
- **Long-lived feature branches per phase**: large, late merges, which are the hardest kind of change to review safely.
- **Committing straight to `trunk`**: true trunk-based, but loses the PR as the record of human review and gate sign-off.
