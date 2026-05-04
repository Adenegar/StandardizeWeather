import pytest

from standardize_weather.db import connect, init_schema
from standardize_weather.stations import UnknownStation, resolve_station_id, set_alias


def _conn(tmp_path):
    conn = connect(tmp_path / "wt.db")
    init_schema(conn)
    return conn


def test_resolve_unknown_raises(tmp_path):
    conn = _conn(tmp_path)
    with pytest.raises(UnknownStation):
        resolve_station_id(conn, "noaa", "KBOI")


def test_set_then_resolve(tmp_path):
    conn = _conn(tmp_path)
    set_alias(
        conn,
        source="noaa",
        source_station_id="KBOI",
        canonical_station_id="BOISE_AIRPORT",
    )
    assert resolve_station_id(conn, "noaa", "KBOI") == "BOISE_AIRPORT"


def test_set_alias_overwrites(tmp_path):
    conn = _conn(tmp_path)
    set_alias(conn, source="noaa", source_station_id="KBOI", canonical_station_id="A")
    set_alias(conn, source="noaa", source_station_id="KBOI", canonical_station_id="B")
    assert resolve_station_id(conn, "noaa", "KBOI") == "B"
