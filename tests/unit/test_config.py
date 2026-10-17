"""Acceptance tests for spec 0001: typed settings loaded from the environment."""

from datetime import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from stormsafe.config import Settings

# Obviously fake site values (ADR 0004): never a real location.
VALID_ENV = {
    "STORMSAFE_SITE_LAT": "0.5",
    "STORMSAFE_SITE_LON": "0.5",
    "STORMSAFE_SITE_TIMEZONE": "Etc/UTC",
    "STORMSAFE_LABEL_RADIUS_MILES": "10",
    "STORMSAFE_FORECAST_HORIZON_MINUTES": "60",
    "STORMSAFE_CLOSURE_DURATION_MINUTES": "30",
    "STORMSAFE_OPERATING_HOURS_START": "10:00",
    "STORMSAFE_OPERATING_HOURS_END": "18:00",
    "STORMSAFE_DATA_DIR": "data",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Start every test from a clean environment holding only VALID_ENV."""
    for key, value in VALID_ENV.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def load() -> Settings:
    # Ignore any local .env so tests depend only on the environment they set.
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_loads_from_env_vars(env: pytest.MonkeyPatch) -> None:
    s = load()
    assert s.site_lat == pytest.approx(0.5)
    assert s.site_lon == pytest.approx(0.5)
    assert s.site_timezone == "Etc/UTC"
    assert s.label_radius_miles == 10
    assert s.forecast_horizon_minutes == 60
    assert s.closure_duration_minutes == 30
    assert s.operating_hours_start == time(10, 0)
    assert s.operating_hours_end == time(18, 0)
    assert s.data_dir == Path("data")


@pytest.mark.parametrize("missing", ["STORMSAFE_SITE_LAT", "STORMSAFE_SITE_LON"])
def test_missing_site_coordinates_fail_clearly(env: pytest.MonkeyPatch, missing: str) -> None:
    env.delenv(missing)
    with pytest.raises(ValidationError) as exc:
        load()
    field = missing.removeprefix("STORMSAFE_").lower()
    assert field in str(exc.value)


@pytest.mark.parametrize(
    "missing",
    [
        "STORMSAFE_SITE_TIMEZONE",
        "STORMSAFE_LABEL_RADIUS_MILES",
        "STORMSAFE_FORECAST_HORIZON_MINUTES",
        "STORMSAFE_CLOSURE_DURATION_MINUTES",
        "STORMSAFE_OPERATING_HOURS_START",
        "STORMSAFE_OPERATING_HOURS_END",
    ],
)
def test_required_values_have_no_defaults(env: pytest.MonkeyPatch, missing: str) -> None:
    env.delenv(missing)
    with pytest.raises(ValidationError):
        load()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("STORMSAFE_SITE_LAT", "91"),
        ("STORMSAFE_SITE_LAT", "-91"),
        ("STORMSAFE_SITE_LON", "181"),
        ("STORMSAFE_SITE_LON", "-181"),
    ],
)
def test_out_of_range_coordinates_rejected(env: pytest.MonkeyPatch, key: str, value: str) -> None:
    env.setenv(key, value)
    with pytest.raises(ValidationError):
        load()


@pytest.mark.parametrize(
    "key",
    [
        "STORMSAFE_LABEL_RADIUS_MILES",
        "STORMSAFE_FORECAST_HORIZON_MINUTES",
        "STORMSAFE_CLOSURE_DURATION_MINUTES",
    ],
)
def test_non_positive_values_rejected(env: pytest.MonkeyPatch, key: str) -> None:
    env.setenv(key, "0")
    with pytest.raises(ValidationError):
        load()


@pytest.mark.parametrize("end", ["10:00", "09:00"])
def test_end_at_or_before_start_rejected(env: pytest.MonkeyPatch, end: str) -> None:
    env.setenv("STORMSAFE_OPERATING_HOURS_END", end)
    with pytest.raises(ValidationError) as exc:
        load()
    assert "operating_hours_end" in str(exc.value)


def test_unknown_timezone_rejected(env: pytest.MonkeyPatch) -> None:
    env.setenv("STORMSAFE_SITE_TIMEZONE", "Mars/Olympus_Mons")
    with pytest.raises(ValidationError) as exc:
        load()
    assert "site_timezone" in str(exc.value)
