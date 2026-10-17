"""Typed settings for StormSafe.

Every value comes from ``STORMSAFE_*`` environment variables or a local ``.env`` file.
Only the data directory has a default:

- Site config (latitude, longitude, time zone) is private and lives only in the
  owner's local ``.env`` or the cluster Secret (ADR 0004).
- The label definition, closure rule, and operating hours are human-only values
  from ``docs/problem-spec.md``, copied into ``.env.example``.
"""

from datetime import time
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, validated at load time."""

    model_config = SettingsConfigDict(
        env_prefix="STORMSAFE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    site_lat: float = Field(ge=-90, le=90, description="Site latitude, degrees (private)")
    site_lon: float = Field(ge=-180, le=180, description="Site longitude, degrees (private)")
    site_timezone: str = Field(description="Site IANA time zone (private)")

    label_radius_miles: float = Field(gt=0, description="Strike radius around the site")
    forecast_horizon_minutes: int = Field(gt=0, description="How far ahead each forecast looks")
    closure_duration_minutes: int = Field(gt=0, description="Closure length after a strike")

    operating_hours_start: time = Field(description="Site local time the pool opens")
    operating_hours_end: time = Field(description="Site local time the pool closes")

    data_dir: Path = Field(default=Path("data"), description="Root for local data files")

    @field_validator("site_timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as err:
            raise ValueError("unknown IANA time zone") from err
        return value

    @model_validator(mode="after")
    def _hours_in_order(self) -> Self:
        if self.operating_hours_end <= self.operating_hours_start:
            raise ValueError("operating_hours_end must be after operating_hours_start")
        return self

    @property
    def tz(self) -> ZoneInfo:
        """The site time zone as a ``ZoneInfo``."""
        return ZoneInfo(self.site_timezone)
