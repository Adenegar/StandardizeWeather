import json
from pathlib import Path

import httpx

from weather_truth.db import connect, init_schema
from weather_truth.feeds.http import HttpClient
from weather_truth.feeds.noaa import NoaaClient
from weather_truth.ingest import ingest_noaa
from weather_truth.stations import resolve_station_id

FIXTURE = Path(__file__).parent / "fixtures" / "noaa_kboi.json"


def _mock_client(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "stations/KBOI/observations/latest" in str(request.url)
        return httpx.Response(200, json=payload)

    return NoaaClient(http=HttpClient(transport=httpx.MockTransport(handler)))


def _setup(tmp_path):
    conn = connect(tmp_path / "wt.db")
    init_schema(conn)
    return conn


def test_writes_canonical_row_and_raw_payload(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    conn = _setup(tmp_path)

    row_id = ingest_noaa(conn, "KBOI", client=_mock_client(payload))

    row = conn.execute(
        "SELECT * FROM observations WHERE id = ?", (row_id,)
    ).fetchone()
    assert row["station_id"] == "KBOI"
    assert row["source"] == "noaa"
    assert row["temp_c"] == 18.2
    assert row["pressure_hpa"] == 1015.0

    raw = conn.execute(
        "SELECT payload_json FROM raw_payloads WHERE source_record_id = ?",
        (row["source_record_id"],),
    ).fetchone()
    assert json.loads(raw["payload_json"]) == payload


def test_self_seeds_alias_for_first_seen_noaa_station(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    conn = _setup(tmp_path)

    ingest_noaa(conn, "KBOI", client=_mock_client(payload))

    assert resolve_station_id(conn, "noaa", "KBOI") == "KBOI"


def test_idempotent_on_repeat(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    conn = _setup(tmp_path)

    id1 = ingest_noaa(conn, "KBOI", client=_mock_client(payload))
    id2 = ingest_noaa(conn, "KBOI", client=_mock_client(payload))

    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) AS c FROM observations").fetchone()["c"]
    assert count == 1
