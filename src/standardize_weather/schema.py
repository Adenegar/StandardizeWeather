from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_validator

Source = Literal["noaa", "openweather", "weatherapi", "pws"]


class Observation(BaseModel):
    """One canonical weather observation. Every feed gets mapped into this shape."""

    station_id: str
    source: Source
    observed_at: datetime
    temp_c: float
    humidity_pct: float | None = None
    pressure_hpa: float | None = None
    precip_mm_1h: float | None = None
    ingested_at: datetime
    source_record_id: str

    @field_validator("observed_at", "ingested_at")
    @classmethod
    def _require_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return v.astimezone(timezone.utc)
