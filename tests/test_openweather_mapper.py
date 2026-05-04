import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from standardize_weather.normalize.openweather import map_openweather_observation

FIXTURE = Path(__file__).parent / "fixtures" / "openweather_kboi.json"
INGESTED_AT = datetime(2026, 5, 4, 15, 24, tzinfo=timezone.utc)


def _payload():
    return json.loads(FIXTURE.read_text())


def test_happy_path():
    payload = _payload()
    obs = map_openweather_observation(
        payload, station_id="KBOI", ingested_at=INGESTED_AT
    )
    assert obs.source == "openweather"
    assert obs.station_id == "KBOI"
    assert obs.temp_c == 15.4
    assert obs.humidity_pct == 45.0
    assert obs.pressure_hpa == 1012.0
    assert obs.precip_mm_1h is None  # no rain key in fixture
    expected = datetime.fromtimestamp(payload["dt"], tz=timezone.utc)
    assert obs.observed_at == expected
    assert obs.source_record_id == f"openweather:5586437:{expected.isoformat()}"


def test_rain_1h_is_picked_up():
    payload = _payload()
    payload["rain"] = {"1h": 0.8}
    obs = map_openweather_observation(
        payload, station_id="KBOI", ingested_at=INGESTED_AT
    )
    assert obs.precip_mm_1h == 0.8


def test_rain_present_but_no_1h_field():
    payload = _payload()
    payload["rain"] = {"3h": 2.5}
    obs = map_openweather_observation(
        payload, station_id="KBOI", ingested_at=INGESTED_AT
    )
    assert obs.precip_mm_1h is None


def test_missing_temp_raises():
    payload = _payload()
    del payload["main"]["temp"]
    with pytest.raises(ValueError, match="missing required temp"):
        map_openweather_observation(
            payload, station_id="KBOI", ingested_at=INGESTED_AT
        )


def test_canonical_station_id_used():
    obs = map_openweather_observation(
        _payload(), station_id="BOISE_AIRPORT", ingested_at=INGESTED_AT
    )
    assert obs.station_id == "BOISE_AIRPORT"
    # source_record_id keeps OpenWeather's city id, since that's what dedupes the feed
    assert "5586437" in obs.source_record_id
