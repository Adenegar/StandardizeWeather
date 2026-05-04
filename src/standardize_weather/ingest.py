from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .db import connect, init_schema, insert_observation, store_raw_payload
from .feeds.noaa import NoaaClient
from .feeds.openweather import OpenWeatherClient
from .normalize.noaa import map_noaa_observation
from .normalize.openweather import map_openweather_observation
from .stations import UnknownStation, resolve_station_id, set_alias


def _existing_observation_id(
    conn: sqlite3.Connection, source: str, source_record_id: str
) -> int | None:
    row = conn.execute(
        "SELECT id FROM observations WHERE source = ? AND source_record_id = ?",
        (source, source_record_id),
    ).fetchone()
    return row["id"] if row else None


def ingest_noaa(
    conn: sqlite3.Connection,
    source_station_id: str,
    *,
    client: NoaaClient | None = None,
) -> int:
    owns_client = client is None
    client = client or NoaaClient()
    try:
        payload = client.latest_observation(source_station_id)
    finally:
        if owns_client:
            client.close()

    try:
        canonical = resolve_station_id(conn, "noaa", source_station_id)
    except UnknownStation:
        # NOAA station IDs are stable and human-readable; for first-seen
        # NOAA stations we self-seed the alias as identity. Other sources
        # use opaque IDs and require explicit seeding.
        set_alias(
            conn,
            source="noaa",
            source_station_id=source_station_id,
            canonical_station_id=source_station_id,
        )
        canonical = source_station_id

    now = datetime.now(timezone.utc)
    obs = map_noaa_observation(payload, station_id=canonical, ingested_at=now)

    store_raw_payload(
        conn,
        source="noaa",
        source_record_id=obs.source_record_id,
        fetched_at=now,
        payload=payload,
    )

    existing = _existing_observation_id(conn, obs.source, obs.source_record_id)
    if existing is not None:
        return existing
    return insert_observation(conn, obs)


def ingest_openweather(
    conn: sqlite3.Connection,
    source_city_id: str,
    *,
    client: OpenWeatherClient | None = None,
) -> int:
    # OpenWeather's station identifier is an opaque integer city id, so we
    # require the alias to be seeded explicitly — no self-seeding here.
    canonical = resolve_station_id(conn, "openweather", source_city_id)

    owns_client = client is None
    client = client or OpenWeatherClient()
    try:
        payload = client.current_by_city_id(source_city_id)
    finally:
        if owns_client:
            client.close()

    now = datetime.now(timezone.utc)
    obs = map_openweather_observation(
        payload, station_id=canonical, ingested_at=now
    )

    store_raw_payload(
        conn,
        source="openweather",
        source_record_id=obs.source_record_id,
        fetched_at=now,
        payload=payload,
    )

    existing = _existing_observation_id(conn, obs.source, obs.source_record_id)
    if existing is not None:
        return existing
    return insert_observation(conn, obs)


def seed_aliases_from_file(conn: sqlite3.Connection, path: Path) -> int:
    entries = json.loads(path.read_text())
    for entry in entries:
        set_alias(
            conn,
            source=entry["source"],
            source_station_id=entry["source_station_id"],
            canonical_station_id=entry["canonical_station_id"],
        )
    return len(entries)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="standardize_weather.ingest")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_noaa = sub.add_parser("noaa", help="Ingest a NOAA station observation")
    p_noaa.add_argument("--station", required=True, help="NOAA station ID, e.g. KBOI")
    p_noaa.add_argument("--db", default="wt.db")

    p_ow = sub.add_parser(
        "openweather", help="Ingest an OpenWeather city observation"
    )
    p_ow.add_argument(
        "--station",
        required=True,
        help="OpenWeather city id, e.g. 5586437 for Boise",
    )
    p_ow.add_argument("--db", default="wt.db")

    p_seed = sub.add_parser(
        "seed-aliases", help="Load station aliases from a JSON file"
    )
    p_seed.add_argument("--file", required=True)
    p_seed.add_argument("--db", default="wt.db")

    return parser


def main(argv: list[str] | None = None) -> int:
    # Auto-load .env so OPENWEATHER_API_KEY etc. are available without exporting.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    args = _build_parser().parse_args(argv)
    conn = connect(Path(args.db))
    init_schema(conn)

    if args.cmd == "noaa":
        row_id = ingest_noaa(conn, args.station)
        print(f"inserted observation id={row_id}")
    elif args.cmd == "openweather":
        row_id = ingest_openweather(conn, args.station)
        print(f"inserted observation id={row_id}")
    elif args.cmd == "seed-aliases":
        n = seed_aliases_from_file(conn, Path(args.file))
        print(f"seeded {n} aliases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
