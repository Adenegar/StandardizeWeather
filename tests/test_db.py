import sqlite3
from datetime import datetime, timezone

import pytest

from standardize_weather.db import (
    connect,
    fetch_observation,
    init_schema,
    insert_observation,
    store_raw_payload,
)
from standardize_weather.schema import Observation


def _conn(tmp_path):
    conn = connect(tmp_path / "wt.db")
    init_schema(conn)
    return conn


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


def test_init_schema_creates_tables(tmp_path):
    conn = _conn(tmp_path)
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"observations", "raw_payloads", "station_aliases"} <= names


def test_observation_round_trip(tmp_path):
    conn = _conn(tmp_path)
    original = _obs()
    row_id = insert_observation(conn, original)
    loaded = fetch_observation(conn, row_id)
    assert loaded == original


def test_duplicate_source_record_id_rejected(tmp_path):
    conn = _conn(tmp_path)
    insert_observation(conn, _obs())
    with pytest.raises(sqlite3.IntegrityError):
        insert_observation(conn, _obs(temp_c=99.0))


def test_raw_payload_storage(tmp_path):
    conn = _conn(tmp_path)
    store_raw_payload(
        conn,
        source="noaa",
        source_record_id="noaa:KBOI:2026-05-04T15:00Z",
        fetched_at=datetime(2026, 5, 4, 15, 1, tzinfo=timezone.utc),
        payload={"temperature": {"value": 18.2, "unitCode": "wmoUnit:degC"}},
    )
    row = conn.execute(
        "SELECT payload_json FROM raw_payloads WHERE source_record_id = ?",
        ("noaa:KBOI:2026-05-04T15:00Z",),
    ).fetchone()
    assert "18.2" in row["payload_json"]


def test_fetch_missing_returns_none(tmp_path):
    conn = _conn(tmp_path)
    assert fetch_observation(conn, 999) is None
