# CLAUDE.md — agent context for StormSafe

## What this project is
StormSafe predicts the probability of a lightning strike within 10 miles of an outdoor pool facility in the next 60 minutes, hourly and on demand, during operating hours (10 AM – 6 PM site time). The pool closes for 30 minutes after any strike within 10 miles. It is a safety system: a missed strike is far worse than an unneeded closure. It is also an MLOps portfolio project, so process artifacts (specs, ADRs, model card, runbook) matter as much as code.

Read `docs/sdlc.md` for the lifecycle and `docs/problem-spec.md` for the problem before doing anything. If the problem spec does not exist yet, Gate 1 has not passed: do not start any work beyond Phase 0.

## Starting a session
The repo is the project's memory; a chat is not. Every session starts from the files:
1. Read this file, then `docs/roadmap.md`.
2. Find the next action and its approved spec in `docs/specs/`.
3. Check open PRs and branches for work already in flight.
4. Follow "How you work here" below.

A decision made in conversation is not real until it is in an ADR, a spec, or the roadmap. If one comes up, propose the file change.

## How you work here
1. You only implement work that has an **approved spec**: `docs/specs/NNNN-short-name/spec.md` with status `approved`. No spec → stop and ask.
2. Before writing code, write **`plan.md`** beside the spec (template in `docs/specs/_template/`), commit it as the first commit on the branch, and wait for the owner's approval. If the implementation departs from the plan, update `plan.md` in the same commit.
3. Write **failing tests first** that encode the spec's acceptance criteria, then implement until they pass.
4. **Trunk-based development** (ADR 0002). Branch off the latest `trunk` as `spec-NNNN-short-name`; the branch should live less than a day. Ship a large spec as several small PRs. Rebase on `trunk` before opening the PR. Unfinished behavior merges behind a config flag that defaults to off. Open the PR using the template. Never merge.
5. **Every PR updates `docs/roadmap.md`** "Next actions" so the repo always says what comes next.
6. Stage files by path; never `git add -A` or `git add .`. Commit no build artifacts, caches, or local data.
7. If the spec is ambiguous or conflicts with an ADR, stop and ask. Do not guess on anything in "Human only" below.
8. Review personas (ADR 0003) advise; they never approve or merge. Address their findings or explain in the PR why not.

## Guardrails

| Area | You may | Human only |
| --- | --- | --- |
| `src/` ingestion, features, serving, monitoring code | Write, refactor | Merge |
| `tests/` | Add tests | Delete, skip, or loosen an existing test or tolerance |
| Label definition (10 mi / next 60 min), 30-min closure rule, operating hours, alert thresholds, recall target (`docs/problem-spec.md`) | Propose in a PR comment | Change values |
| `docs/problem-spec.md`, `docs/adr/` | Draft when asked | Accept / change status |
| `.github/workflows/train.yml`, `deploy.yml` | Read | Edit, trigger |
| Model registry stage changes (shadow → production) | Nothing | All |
| `.claude/agents/` personas (ADR 0003) | Draft when asked | Accept; change a persona's tools or permissions |
| Site location: latitude, longitude, time zone (ADR 0004) | Never write it into the repo, PRs, commit messages, or logs | Set it in local `.env` and the cluster Secret |
| Infra config in the repo: `deploy/` manifests, cluster config, `Dockerfile` | Draft in a PR | Accept; apply it to a cluster; change the deployed image digest (a release, ADR 0007) |
| Anything run against a live cluster: bootstrap scripts, `kubectl apply`, Argo CD syncs and rollbacks | Nothing | All |
| Secrets, cloud credentials | Nothing | All |

If a change touches anything in the "Human only" column, say so explicitly at the top of the PR description.

## Conventions (set by spec 0001)
- Python 3.12, `uv` for env and deps, `src/` layout, package `stormsafe`
- `ruff` (lint + format), `mypy --strict` on `src/`, `pytest`
- Config via typed settings (pydantic-settings); no hard-coded paths or thresholds in code
- Data pipelines write intermediate results to disk in chunks (e.g., one Parquet file per day) so long runs can resume
- Every function that touches time uses timezone-aware UTC datetimes

## Commands
- Setup: `uv sync`, then `cp .env.example .env` and fill in the site values (private, ADR 0004)
- Test: `uv run pytest`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Format: `uv run ruff format .`
- Types: `uv run mypy src`
- Everything CI runs: `uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`
