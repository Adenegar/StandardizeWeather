import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from weather_truth.normalize.noaa import map_noaa_observation

FIXTURE = Path(__file__).parent / "fixtures" / "noaa_kboi.json"
INGESTED_AT = datetime(2026, 5, 4, 15, 1, tzinfo=timezone.utc)


def _payload():
    return json.loads(FIXTURE.read_text())


def test_happy_path():
    obs = map_noaa_observation(_payload(), station_id="KBOI", ingested_at=INGESTED_AT)
    assert obs.source == "noaa"
    assert obs.station_id == "KBOI"
    assert obs.temp_c == 18.2
    assert obs.humidity_pct == 42.0
    assert obs.pressure_hpa == 1015.0
    assert obs.precip_mm_1h is None
    assert obs.observed_at == datetime(2026, 5, 4, 15, 0, tzinfo=timezone.utc)
    assert obs.source_record_id == "noaa:KBOI:2026-05-04T15:00:00+00:00"


def test_null_humidity_becomes_none():
    payload = _payload()
    payload["properties"]["relativeHumidity"]["value"] = None
    obs = map_noaa_observation(payload, station_id="KBOI", ingested_at=INGESTED_AT)
    assert obs.humidity_pct is None


def test_sentinel_minus_9999_treated_as_missing():
    payload = _payload()
    payload["properties"]["barometricPressure"]["value"] = -9999
    obs = map_noaa_observation(payload, station_id="KBOI", ingested_at=INGESTED_AT)
    assert obs.pressure_hpa is None


def test_non_utc_timestamp_normalized():
    payload = _payload()
    payload["properties"]["timestamp"] = "2026-05-04T08:00:00-07:00"
    obs = map_noaa_observation(payload, station_id="KBOI", ingested_at=INGESTED_AT)
    assert obs.observed_at == datetime(2026, 5, 4, 15, 0, tzinfo=timezone.utc)


def test_canonical_station_id_passed_through():
    obs = map_noaa_observation(
        _payload(), station_id="BOISE_AIRPORT", ingested_at=INGESTED_AT
    )
    assert obs.station_id == "BOISE_AIRPORT"
    # source_record_id still uses NOAA's id, since that's what dedupes the feed
    assert "KBOI" in obs.source_record_id


def test_unexpected_unit_raises():
    payload = _payload()
    payload["properties"]["temperature"]["unitCode"] = "wmoUnit:degF"
    with pytest.raises(ValueError, match="unexpected NOAA unit"):
        map_noaa_observation(payload, station_id="KBOI", ingested_at=INGESTED_AT)


def test_missing_temperature_raises():
    payload = _payload()
    payload["properties"]["temperature"]["value"] = None
    with pytest.raises(ValueError, match="missing required temperature"):
        map_noaa_observation(payload, station_id="KBOI", ingested_at=INGESTED_AT)
