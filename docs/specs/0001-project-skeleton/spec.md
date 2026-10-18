# Spec 0001 — Project skeleton and CI

**Status:** approved
**Phase:** 0

## Goal
An installable, empty `stormsafe` package with linting, type checking, tests, typed config, and a CI workflow that runs all of them on every PR and every push to `trunk`.

## Inputs / outputs
- Creates: `pyproject.toml`, `uv.lock`, `.python-version`, `src/stormsafe/__init__.py`, `src/stormsafe/py.typed`, `src/stormsafe/config.py`, `.env.example`, `tests/unit/`, `.github/workflows/ci.yml`
- `config.py` exposes a pydantic-settings `Settings`, read from `STORMSAFE_*` environment variables or a local `.env`:
  - **Site config (ADR 0004):** site latitude, longitude, and time zone. Required, no defaults.
  - **Problem-spec values:** label radius (miles), forecast horizon (minutes), closure duration (minutes), operating hours start and end (site local time). Required, no defaults.
  - **Data directory:** defaults to `data`.
- `.env.example` lists every key. Site keys are blank; problem-spec values are copied from `docs/problem-spec.md`.

## Acceptance criteria
- [ ] `uv sync` installs on Python 3.12
- [ ] `Settings` loads from env vars (test)
- [ ] Missing site latitude or longitude fails with an error naming the field (test)
- [ ] Every value without a default fails clearly when missing (test)
- [ ] Out-of-range coordinates, non-positive durations, end hour at or before start hour, and unknown time zones are rejected (tests)
- [ ] Tests use obviously fake site values, never a real location
- [ ] `.env.example` has blank site values (test)
- [ ] **Site guard:** when a local `.env` exists, a test fails if any tracked file contains its site values; without a `.env` (as in CI) the test is skipped (ADR 0004)
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src` (strict) pass
- [ ] `ci.yml` runs install, lint, format check, types, and tests on every PR to `trunk` and every push to `trunk`, with read-only permissions
- [ ] `CLAUDE.md` "Commands" section filled in

## Out of scope
- Any data ingestion, modeling, or serving code
- `train.yml`, `deploy.yml`, the AI review workflow

## Human-only touchpoints
- Site values: the owner sets them in their local `.env` only.
- Problem-spec values in `.env.example` are copied, never changed, by the agent.

## Open questions
- None
