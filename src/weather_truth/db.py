from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import Observation

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS observations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id       TEXT NOT NULL,
    source           TEXT NOT NULL,
    observed_at      TEXT NOT NULL,
    temp_c           REAL NOT NULL,
    humidity_pct     REAL,
    pressure_hpa     REAL,
    precip_mm_1h     REAL,
    ingested_at      TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    UNIQUE (source, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_observations_station_time
    ON observations(station_id, observed_at);

CREATE TABLE IF NOT EXISTS raw_payloads (
    source           TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    fetched_at       TEXT NOT NULL,
    payload_json     TEXT NOT NULL,
    PRIMARY KEY (source, source_record_id)
);

CREATE TABLE IF NOT EXISTS station_aliases (
    source               TEXT NOT NULL,
    source_station_id    TEXT NOT NULL,
    canonical_station_id TEXT NOT NULL,
    PRIMARY KEY (source, source_station_id)
);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def insert_observation(conn: sqlite3.Connection, obs: Observation) -> int:
    cur = conn.execute(
        """
        INSERT INTO observations
            (station_id, source, observed_at, temp_c, humidity_pct,
             pressure_hpa, precip_mm_1h, ingested_at, source_record_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            obs.station_id,
            obs.source,
            obs.observed_at.isoformat(),
            obs.temp_c,
            obs.humidity_pct,
            obs.pressure_hpa,
            obs.precip_mm_1h,
            obs.ingested_at.isoformat(),
            obs.source_record_id,
        ),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def fetch_observation(conn: sqlite3.Connection, row_id: int) -> Observation | None:
    row = conn.execute(
        "SELECT * FROM observations WHERE id = ?", (row_id,)
    ).fetchone()
    if row is None:
        return None
    return Observation(
        station_id=row["station_id"],
        source=row["source"],
        observed_at=row["observed_at"],
        temp_c=row["temp_c"],
        humidity_pct=row["humidity_pct"],
        pressure_hpa=row["pressure_hpa"],
        precip_mm_1h=row["precip_mm_1h"],
        ingested_at=row["ingested_at"],
        source_record_id=row["source_record_id"],
    )


def store_raw_payload(
    conn: sqlite3.Connection,
    *,
    source: str,
    source_record_id: str,
    fetched_at: datetime,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO raw_payloads
            (source, source_record_id, fetched_at, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (source, source_record_id, fetched_at.isoformat(), json.dumps(payload)),
    )
    conn.commit()
