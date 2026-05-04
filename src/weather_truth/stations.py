from __future__ import annotations

import sqlite3


class UnknownStation(Exception):
    pass


def set_alias(
    conn: sqlite3.Connection,
    *,
    source: str,
    source_station_id: str,
    canonical_station_id: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO station_aliases
            (source, source_station_id, canonical_station_id)
        VALUES (?, ?, ?)
        """,
        (source, source_station_id, canonical_station_id),
    )
    conn.commit()


def resolve_station_id(
    conn: sqlite3.Connection, source: str, source_station_id: str
) -> str:
    row = conn.execute(
        """
        SELECT canonical_station_id
        FROM station_aliases
        WHERE source = ? AND source_station_id = ?
        """,
        (source, source_station_id),
    ).fetchone()
    if row is None:
        raise UnknownStation(f"no alias for {source}:{source_station_id}")
    return row["canonical_station_id"]
