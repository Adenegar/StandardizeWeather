from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from standardize_weather.schema import Observation


def _obs(**kw):
    base = dict(
        station_id="KBOI",
        source="noaa",
        observed_at=datetime(2026, 5, 4, 15, 0, tzinfo=timezone.utc),
        temp_c=18.2,
        humidity_pct=42.0,
        pressure_hpa=1015.0,
        precip_mm_1h=0.0,
        ingested_at=datetime(2026, 5, 4, 15, 1, tzinfo=timezone.utc),
        source_record_id="noaa:KBOI:2026-05-04T15:00Z",
    )
    base.update(kw)
    return Observation(**base)


def test_construct_minimum():
    obs = _obs()
    assert obs.station_id == "KBOI"
    assert obs.temp_c == 18.2


def test_optional_fields_default_none():
    obs = _obs(humidity_pct=None, pressure_hpa=None, precip_mm_1h=None)
    assert obs.humidity_pct is None
    assert obs.pressure_hpa is None
    assert obs.precip_mm_1h is None


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        _obs(observed_at=datetime(2026, 5, 4, 15, 0))


def test_non_utc_datetime_normalized_to_utc():
    mountain = timezone(timedelta(hours=-7))
    obs = _obs(observed_at=datetime(2026, 5, 4, 8, 0, tzinfo=mountain))
    assert obs.observed_at.tzinfo == timezone.utc
    assert obs.observed_at.hour == 15


def test_unknown_source_rejected():
    with pytest.raises(ValidationError):
        _obs(source="bogus")
