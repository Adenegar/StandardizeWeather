from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..schema import Observation
from ..units import pa_to_hpa

# Some legacy NWS feeds use this sentinel for missing values. NOAA's
# api.weather.gov mostly uses null, but we treat both as missing to be safe.
SENTINEL_MISSING = -9999


def _value(field: dict[str, Any] | None, *, expected_unit: str) -> float | None:
    if field is None:
        return None
    v = field.get("value")
    if v is None or v == SENTINEL_MISSING:
        return None
    unit = field.get("unitCode", "")
    if not unit.endswith(expected_unit):
        raise ValueError(f"unexpected NOAA unit {unit!r}, wanted {expected_unit!r}")
    return float(v)


def _source_station_id(payload: dict[str, Any]) -> str:
    station_url = payload["properties"]["station"]
    return station_url.rsplit("/", 1)[-1]


def map_noaa_observation(
    payload: dict[str, Any],
    *,
    station_id: str,
    ingested_at: datetime,
) -> Observation:
    """Map a NOAA stations/{id}/observations/latest payload to an Observation.

    `station_id` is the canonical id (alias resolution happens upstream).
    """
    props = payload["properties"]
    observed_at = datetime.fromisoformat(props["timestamp"]).astimezone(timezone.utc)

    temp_c = _value(props.get("temperature"), expected_unit="degC")
    if temp_c is None:
        raise ValueError("NOAA payload missing required temperature value")

    humidity = _value(props.get("relativeHumidity"), expected_unit="percent")
    pressure_pa = _value(props.get("barometricPressure"), expected_unit="Pa")
    pressure_hpa = pa_to_hpa(pressure_pa) if pressure_pa is not None else None
    precip = _value(props.get("precipitationLastHour"), expected_unit="mm")

    src_station = _source_station_id(payload)
    record_id = f"noaa:{src_station}:{observed_at.isoformat()}"

    return Observation(
        station_id=station_id,
        source="noaa",
        observed_at=observed_at,
        temp_c=temp_c,
        humidity_pct=humidity,
        pressure_hpa=pressure_hpa,
        precip_mm_1h=precip,
        ingested_at=ingested_at,
        source_record_id=record_id,
    )
