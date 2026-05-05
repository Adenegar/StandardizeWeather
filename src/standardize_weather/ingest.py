from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import insert_observation, store_raw_payload
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


