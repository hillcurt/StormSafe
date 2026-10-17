# Plan for spec 0001 — Project skeleton and CI

**Spec:** `docs/specs/0001-project-skeleton/spec.md`
**Status:** done

## Approach
A minimal `uv` project with a `src/` layout and a single typed `Settings` class. Every required value fails loudly when missing. CI runs the same commands a developer runs locally.

## Files
| File | Create / change | Why |
| --- | --- | --- |
| `pyproject.toml`, `uv.lock`, `.python-version` | Create | Package metadata, pinned dependencies, Python 3.12; ruff and strict mypy configured in `pyproject.toml` |
| `src/stormsafe/__init__.py`, `py.typed` | Create | Installable, typed package |
| `src/stormsafe/config.py` | Create | `Settings` (pydantic-settings), prefix `STORMSAFE_`, `.env` support, validation |
| `.env.example` | Create | Every key; site keys blank; problem-spec values copied |
| `tests/unit/test_config.py` | Create | Settings behavior |
| `tests/unit/test_site_privacy.py` | Create | Blank site keys in `.env.example`; site guard (ADR 0004) |
| `.github/workflows/ci.yml` | Create | Install, lint, format check, types, tests; read-only permissions |
| `CLAUDE.md` | Change | Fill in "Commands" |
| `docs/roadmap.md` | Change | Next actions |

## Tests (written first)
1. Settings load from env vars → `test_loads_from_env_vars`
2. Missing site latitude or longitude names the field → `test_missing_site_coordinates_fail_clearly`
3. Every value without a default is required → `test_required_values_have_no_defaults`
4. Validation: out-of-range coordinates, non-positive durations, end at or before start, unknown time zone → one test each
5. Fake site values only → the fixture uses coordinates (0.5, 0.5) and time zone `Etc/UTC`
6. Blank site keys in `.env.example` → `test_env_example_has_blank_site_values`
7. Site guard → `test_no_tracked_file_contains_local_site_values`, skipped without a local `.env`
8. Lint, format, and types → CI steps

## PR slicing
One PR.

## Risks and open questions
- The site guard only protects the owner's machine (CI has no `.env`). Pair it with secret scanning and the reviewer persona.
