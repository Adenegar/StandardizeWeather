from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .db import connect, init_schema, insert_observation, store_raw_payload
from .feeds.noaa import NoaaClient
from .normalize.noaa import map_noaa_observation
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
        # will require explicit seeding before ingest.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="weather_truth.ingest")
    parser.add_argument("source", choices=["noaa"])
    parser.add_argument("--station", required=True)
    parser.add_argument("--db", default="wt.db")
    args = parser.parse_args(argv)

    conn = connect(Path(args.db))
    init_schema(conn)
    if args.source == "noaa":
        row_id = ingest_noaa(conn, args.station)
        print(f"inserted observation id={row_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
