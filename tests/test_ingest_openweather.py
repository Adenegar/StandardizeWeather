import json
from pathlib import Path

import httpx
import pytest

from weather_truth.db import connect, init_schema
from weather_truth.feeds.http import HttpClient
from weather_truth.feeds.openweather import OpenWeatherAuthError, OpenWeatherClient
from weather_truth.ingest import ingest_openweather, seed_aliases_from_file
from weather_truth.stations import UnknownStation, set_alias

FIXTURE = Path(__file__).parent / "fixtures" / "openweather_kboi.json"
SEEDS = Path(__file__).parent.parent / "seeds" / "aliases.json"


def _mock_client(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert "data/2.5/weather" in url
        assert "id=5586437" in url
        assert "units=metric" in url
        return httpx.Response(200, json=payload)

    return OpenWeatherClient(
        api_key="test-key",
        http=HttpClient(transport=httpx.MockTransport(handler)),
    )


def _setup(tmp_path):
    conn = connect(tmp_path / "wt.db")
    init_schema(conn)
    return conn


def test_requires_alias_seeded(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    conn = _setup(tmp_path)
    with pytest.raises(UnknownStation):
        ingest_openweather(conn, "5586437", client=_mock_client(payload))


def test_writes_canonical_row_with_alias(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    conn = _setup(tmp_path)
    set_alias(
        conn,
        source="openweather",
        source_station_id="5586437",
        canonical_station_id="KBOI",
    )

    row_id = ingest_openweather(conn, "5586437", client=_mock_client(payload))

    row = conn.execute(
        "SELECT * FROM observations WHERE id = ?", (row_id,)
    ).fetchone()
    assert row["station_id"] == "KBOI"
    assert row["source"] == "openweather"
    assert row["temp_c"] == 15.4

    raw = conn.execute(
        "SELECT payload_json FROM raw_payloads WHERE source_record_id = ?",
        (row["source_record_id"],),
    ).fetchone()
    assert json.loads(raw["payload_json"]) == payload


def test_idempotent(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    conn = _setup(tmp_path)
    set_alias(
        conn,
        source="openweather",
        source_station_id="5586437",
        canonical_station_id="KBOI",
    )

    id1 = ingest_openweather(conn, "5586437", client=_mock_client(payload))
    id2 = ingest_openweather(conn, "5586437", client=_mock_client(payload))

    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) AS c FROM observations").fetchone()["c"]
    assert count == 1


def test_seed_aliases_file_loads_repo_seeds(tmp_path):
    conn = _setup(tmp_path)
    n = seed_aliases_from_file(conn, SEEDS)
    assert n >= 1
    row = conn.execute(
        """
        SELECT canonical_station_id FROM station_aliases
        WHERE source = ? AND source_station_id = ?
        """,
        ("openweather", "5586437"),
    ).fetchone()
    assert row["canonical_station_id"] == "KBOI"


def test_client_errors_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    with pytest.raises(OpenWeatherAuthError):
        OpenWeatherClient()
