import json
from datetime import datetime, timezone

from standardize_weather.cli import main as cli_main
from standardize_weather.db import connect, init_schema, insert_observation
from standardize_weather.schema import Observation


def _seed_file(tmp_path):
    p = tmp_path / "aliases.json"
    p.write_text(
        json.dumps(
            [
                {
                    "source": "noaa",
                    "source_station_id": "KBOI",
                    "canonical_station_id": "KBOI",
                },
                {
                    "source": "openweather",
                    "source_station_id": "5586437",
                    "canonical_station_id": "KBOI",
                },
            ]
        )
    )
    return p


def test_seed_aliases_loads_file(tmp_path, capsys):
    seeds = _seed_file(tmp_path)
    db = tmp_path / "wt.db"
    rc = cli_main(["seed-aliases", "--file", str(seeds), "--db", str(db)])
    assert rc == 0
    assert "seeded 2" in capsys.readouterr().out


def test_seed_aliases_missing_file_errors(tmp_path, capsys):
    db = tmp_path / "wt.db"
    rc = cli_main(["seed-aliases", "--file", str(tmp_path / "nope.json"), "--db", str(db)])
    assert rc == 1
    assert "seed file not found" in capsys.readouterr().err


def test_ingest_no_station_with_no_seeds_errors(tmp_path, capsys):
    db = tmp_path / "wt.db"
    rc = cli_main(["ingest", "noaa", "--db", str(db)])
    assert rc == 1
    assert "no noaa stations seeded" in capsys.readouterr().err


def test_reconcile_no_data(tmp_path, capsys):
    db = tmp_path / "wt.db"
    rc = cli_main(["reconcile", "--db", str(db)])
    assert rc == 0
    assert "no observations" in capsys.readouterr().out


def test_reconcile_prints_breakdown_with_two_sources(tmp_path, capsys):
    db_path = tmp_path / "wt.db"
    conn = connect(db_path)
    init_schema(conn)

    def _obs(source, **kw):
        base = dict(
            station_id="KBOI",
            source=source,
            observed_at=datetime(2026, 5, 4, 16, tzinfo=timezone.utc),
            temp_c=17.0,
            humidity_pct=45.0,
            pressure_hpa=1010.0,
            ingested_at=datetime(2026, 5, 4, 16, 1, tzinfo=timezone.utc),
            source_record_id=f"{source}:KBOI:16",
        )
        base.update(kw)
        return Observation(**base)

    insert_observation(conn, _obs("noaa"))
    insert_observation(conn, _obs("openweather", temp_c=18.0, humidity_pct=48.0))
    conn.close()

    rc = cli_main(["reconcile", "--db", str(db_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "KBOI" in out
    assert "noaa" in out
    assert "openweather" in out
    assert "median" in out
