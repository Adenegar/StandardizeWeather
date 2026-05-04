from datetime import datetime, timedelta, timezone

from standardize_weather.db import connect, init_schema, insert_observation
from standardize_weather.reconcile import (
    SourceObs,
    format_station_report,
    latest_per_source,
    reconcile_station,
)
from standardize_weather.schema import Observation


def _obs(source, station, **kw):
    base = dict(
        station_id=station,
        source=source,
        observed_at=datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc),
        temp_c=17.0,
        humidity_pct=45.0,
        pressure_hpa=1010.0,
        precip_mm_1h=None,
        ingested_at=datetime(2026, 5, 4, 16, 1, tzinfo=timezone.utc),
        source_record_id=f"{source}:{station}:{datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc).isoformat()}",
    )
    base.update(kw)
    return Observation(**base)


def _conn(tmp_path):
    conn = connect(tmp_path / "wt.db")
    init_schema(conn)
    return conn


def test_latest_per_source_picks_newest_observation(tmp_path):
    conn = _conn(tmp_path)
    older = _obs("noaa", "KBOI", temp_c=10.0, observed_at=datetime(2026, 5, 4, 14, 0, tzinfo=timezone.utc),
                 source_record_id="noaa:KBOI:14")
    newer = _obs("noaa", "KBOI", temp_c=17.0, observed_at=datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc),
                 source_record_id="noaa:KBOI:16")
    insert_observation(conn, older)
    insert_observation(conn, newer)

    grouped = latest_per_source(conn)
    assert list(grouped.keys()) == ["KBOI"]
    assert len(grouped["KBOI"]) == 1
    assert grouped["KBOI"][0].temp_c == 17.0


def test_latest_per_source_groups_by_station(tmp_path):
    conn = _conn(tmp_path)
    insert_observation(conn, _obs("noaa", "KBOI"))
    insert_observation(conn, _obs("openweather", "KBOI", source_record_id="ow:KBOI:16"))
    insert_observation(conn, _obs("noaa", "KSFO", source_record_id="noaa:KSFO:16"))

    grouped = latest_per_source(conn)
    assert set(grouped.keys()) == {"KBOI", "KSFO"}
    assert {s.source for s in grouped["KBOI"]} == {"noaa", "openweather"}
    assert {s.source for s in grouped["KSFO"]} == {"noaa"}


def test_latest_per_source_filters_by_station(tmp_path):
    conn = _conn(tmp_path)
    insert_observation(conn, _obs("noaa", "KBOI"))
    insert_observation(conn, _obs("noaa", "KSFO", source_record_id="noaa:KSFO:16"))

    grouped = latest_per_source(conn, station_id="KBOI")
    assert list(grouped.keys()) == ["KBOI"]


def _src(name, **kw):
    base = dict(temp_c=17.0, humidity_pct=45.0, pressure_hpa=1010.0,
                observed_at="2026-05-04T16:00:00+00:00")
    base.update(kw)
    return SourceObs(source=name, **base)


def test_reconcile_two_close_sources_no_break():
    sources = [_src("noaa", temp_c=17.0), _src("openweather", temp_c=18.0)]
    report = reconcile_station("KBOI", sources)
    assert report.medians["temp_c"] == 17.5
    assert report.has_breaks is False


def test_reconcile_outlier_flagged():
    sources = [
        _src("noaa", temp_c=17.0),
        _src("openweather", temp_c=17.5),
        _src("pws", temp_c=25.0),  # 7.5°C above median, > 1.5°C tolerance
    ]
    report = reconcile_station("KBOI", sources)
    assert report.medians["temp_c"] == 17.5
    pws_deltas = {d.field: d for d in report.deltas["pws"]}
    assert pws_deltas["temp_c"].is_break is True
    noaa_deltas = {d.field: d for d in report.deltas["noaa"]}
    assert noaa_deltas["temp_c"].is_break is False
    assert report.has_breaks is True


def test_reconcile_handles_missing_field():
    sources = [
        _src("noaa", humidity_pct=None),
        _src("openweather", humidity_pct=50.0),
    ]
    report = reconcile_station("KBOI", sources)
    # median computed from available values only
    assert report.medians["humidity_pct"] == 50.0
    noaa_hum = next(d for d in report.deltas["noaa"] if d.field == "humidity_pct")
    assert noaa_hum.delta is None
    assert noaa_hum.is_break is False


def test_reconcile_single_source_no_breaks():
    report = reconcile_station("KBOI", [_src("noaa")])
    assert report.has_breaks is False


def test_format_includes_break_marker_when_break():
    sources = [
        _src("noaa", temp_c=17.0),
        _src("openweather", temp_c=17.5),
        _src("pws", temp_c=25.0),
    ]
    report = reconcile_station("KBOI", sources)
    out = format_station_report(report)
    assert "BREAK" in out
    assert "temp_c" in out
    assert "pws" in out


def test_format_says_no_breaks_when_clean():
    sources = [_src("noaa", temp_c=17.0), _src("openweather", temp_c=18.0)]
    report = reconcile_station("KBOI", sources)
    out = format_station_report(report)
    assert "no breaks" in out
    assert "BREAK" not in out


def test_format_single_source_message():
    report = reconcile_station("KBOI", [_src("noaa")])
    out = format_station_report(report)
    assert "only one source" in out
