from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..schema import Observation


def map_openweather_observation(
    payload: dict[str, Any],
    *,
    station_id: str,
    ingested_at: datetime,
) -> Observation:
    """Map an OpenWeather /weather payload to a canonical Observation.

    Assumes the request was made with units=metric (pinned in the client) so
    temp is already Celsius. The OpenWeather response does not echo the units,
    so this assumption is enforced upstream rather than verified here.
    """
    main = payload["main"]

    observed_at = datetime.fromtimestamp(payload["dt"], tz=timezone.utc)

    temp = main.get("temp")
    if temp is None:
        raise ValueError("OpenWeather payload missing required temp value")

    humidity = main.get("humidity")
    pressure = main.get("pressure")
    rain = payload.get("rain") or {}
    precip = rain.get("1h")

    source_city_id = str(payload["id"])
    record_id = f"openweather:{source_city_id}:{observed_at.isoformat()}"

    return Observation(
        station_id=station_id,
        source="openweather",
        observed_at=observed_at,
        temp_c=float(temp),
        humidity_pct=float(humidity) if humidity is not None else None,
        pressure_hpa=float(pressure) if pressure is not None else None,
        precip_mm_1h=float(precip) if precip is not None else None,
        ingested_at=ingested_at,
        source_record_id=record_id,
    )
