# StormSafe AI SDLC

Two tracks run together. **Track A** is the ML lifecycle: each phase ends in an artifact and a gate. **Track B** is how code gets written: agents implement from specs, humans own gates.

## Track A — ML lifecycle with gates

Nothing moves to the next phase until its gate passes. Monitoring misses loop back to Phase 2.

| Phase | Artifact | Gate passes when | Approver |
| --- | --- | --- | --- |
| 0 Foundations | `CLAUDE.md`, this file, project skeleton, `ci.yml` | CI runs green on an empty package; `trunk` protected per "Trunk-based development" below | Human |
| 1 Frame | `docs/problem-spec.md` | Decision, error costs, label definition, and recall target are written and signed off **before any modeling** | Human |
| 2 Data | `docs/data-contract.md`, ingestion + label code | Schema/freshness checks pass; label builder unit-tested; a 3-day pull runs clean and resumes after interruption | CI + human |
| 3 Develop | MLflow runs | Model beats both baselines (a CAPE-threshold rule and persistence) on a time-based holdout | CI |
| 4 Evaluate | `docs/model-card.md` | Meets recall target at the chosen threshold; no regression vs. the current model; calibration checked; failure modes and seasonality documented | CI + human |
| 5 Deploy | Shadow prediction log | Shadow-mode metrics match offline metrics over an agreed window | Human |
| 6 Monitor | `docs/runbook.md`, nightly outcomes job | Drift and outcome-miss escalation bands defined (1σ log; 2σ read-only diagnosis; 3σ the agent may propose a PR), alerting works, rollback rehearsed; each breach becomes an `intent.md` that re-enters the loop | Human |

**Governance throughout:** versioned data snapshots, MLflow model registry stages, ADRs for every decision that trades safety against cost.

## Track B — AI-assisted development loop

Each change leaves a chain of committed artifacts, one folder per spec: `docs/specs/NNNN-short-name/spec.md` → `plan.md` → tests and code → a reviewed PR. The commit history is the audit trail.

1. **Spec** (human) — `spec.md` from `docs/specs/_template/`. Status `draft` → `approved`.
2. **Plan** (agent drafts, human approves) — `plan.md` beside the spec: files, tests, PR slicing, open questions. Committed as the first commit on the branch, before any code, and kept current: a departure from the plan updates `plan.md` in the same commit.
3. **Tests first** (agent) — failing tests encoding acceptance criteria.
4. **Implement** (agent) — until tests pass, on a short-lived branch off `trunk`.
5. **Review** (automated) — `ci.yml` checks, plus an advisory review by the read-only `reviewer` persona against `REVIEW.md` (`.claude/agents/reviewer.md`, run on every PR by `ai-review.yml`; ADR 0003). The agent addresses its findings or explains why not.
6. **Merge** (human) — read the diff, merge. No auto-merge.

Rules that must always hold are enforced by tests, CI checks, or hooks, not by instructions alone.

Guardrails for what agents may touch live in `CLAUDE.md`.

## Trunk-based development

`trunk` is the only long-lived branch and is always releasable (ADR 0002). It is also the repo's default branch.

- **Short-lived branches.** Branch off the latest `trunk`; merge within a day. No `develop` or `release/*` branches.
- **Small PRs.** A spec that would take more than a day ships as several PRs.
- **Feature flags for unfinished work.** Incomplete behavior merges behind a config flag that defaults to off. Shadow mode in Phase 5 is itself a flag.
- **Protected `trunk`.** A PR is required, CI must pass, merges are squashed into a linear history, and branches are deleted after merge.
- **Release from trunk.** Deploys use a tagged commit on `trunk` (`vX.Y.Z`); rollback means redeploying the previous tag.
- **Gate sign-offs are PRs.** Approving a gate means approving the PR that flips its artifact's status.

## Workflows (built across phases)

| Workflow | Trigger | Does |
| --- | --- | --- |
| `ci.yml` | every PR and every push to `trunk` | lint, types, tests, data-contract checks |
| `train.yml` | manual | retrain, log to MLflow, metric-regression gate |
| `build.yml` | every PR (build only); push to `trunk` and `vX.Y.Z` tags (build and push) | container image to GHCR, tagged by commit or release (ADR 0006) |
| `deploy.yml` | manual + approval | promote registry stage; open the release PR that sets the image digest for Argo CD (ADR 0007) |
| nightly outcomes job | nightly | join yesterday's predictions to observed GLM strikes; log recall, precision, and coverage |
