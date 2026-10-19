"""Acceptance tests for spec 0001: the site location never enters the repo (ADR 0004)."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITE_KEYS = ("STORMSAFE_SITE_LAT", "STORMSAFE_SITE_LON", "STORMSAFE_SITE_TIMEZONE")


def read_env(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines, ignoring blanks and comments."""
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, text=True
    ).stdout
    return [ROOT / name for name in out.split("\0") if name]


def test_env_example_has_blank_site_values() -> None:
    example = read_env(ROOT / ".env.example")
    for key in SITE_KEYS:
        assert key in example, f".env.example must list {key}"
        assert example[key] == "", f"{key} must be blank in .env.example"


def test_no_tracked_file_contains_local_site_values() -> None:
    """Runs on the owner's machine; CI has no .env and skips it."""
    local_env = ROOT / ".env"
    if not local_env.exists():
        pytest.skip("no local .env (expected in CI)")
    site = {k: v for k, v in read_env(local_env).items() if k in SITE_KEYS}
    # Very short values (e.g. "0") would match everywhere; real coordinates are longer.
    needles = [v for v in site.values() if len(v) >= 4]
    if not needles:
        pytest.skip("no site values set in local .env")

    leaks = []
    for path in tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        leaks += [str(path.relative_to(ROOT)) for needle in needles if needle in text]
    assert leaks == [], f"site values found in tracked files: {sorted(set(leaks))}"
