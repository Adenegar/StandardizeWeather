from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from .db import connect, init_schema
from .feeds.openweather import OpenWeatherAuthError
from .ingest import ingest_noaa, ingest_openweather, seed_aliases_from_file
from .reconcile import (
    format_station_report,
    latest_per_source,
    reconcile_station,
)
from .stations import list_source_station_ids

DEFAULT_DB = "wt.db"
DEFAULT_SEEDS = "seeds/aliases.json"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _connect(db_path: str) -> sqlite3.Connection:
    conn = connect(Path(db_path))
    init_schema(conn)
    return conn


def cmd_seed_aliases(args: argparse.Namespace) -> int:
    seed_path = Path(args.file)
    if not seed_path.exists():
        print(f"seed file not found: {seed_path}", file=sys.stderr)
        return 1
    conn = _connect(args.db)
    n = seed_aliases_from_file(conn, seed_path)
    print(f"seeded {n} aliases from {seed_path}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    conn = _connect(args.db)
    if args.station:
        stations = [args.station]
    else:
        stations = list_source_station_ids(conn, args.source)
        if not stations:
            print(
                f"no {args.source} stations seeded. "
                f"run `sw seed-aliases` or pass a station id explicitly.",
                file=sys.stderr,
            )
            return 1

    handler = {"noaa": ingest_noaa, "openweather": ingest_openweather}[args.source]
    for station in stations:
        try:
            row_id = handler(conn, station)
            print(f"{args.source:<12} {station:<10} -> id={row_id}")
        except OpenWeatherAuthError as e:
            print(f"openweather: {e}", file=sys.stderr)
            return 2
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    conn = _connect(args.db)
    grouped = latest_per_source(conn, station_id=args.station)
    if not grouped:
        suffix = f" for station {args.station}" if args.station else ""
        print(f"no observations in {args.db}{suffix}")
        return 0
    blocks = [
        format_station_report(reconcile_station(station_id, sources))
        for station_id, sources in grouped.items()
    ]
    print("\n\n".join(blocks))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    seed_path = Path(args.seeds)
    if not seed_path.exists():
        print(f"seed file not found: {seed_path}", file=sys.stderr)
        return 1
    conn = _connect(args.db)
    n = seed_aliases_from_file(conn, seed_path)
    print(f"seeded {n} aliases from {seed_path}")
    print()

    have_ow_key = bool(os.environ.get("OPENWEATHER_API_KEY"))
    sources_to_run = ["noaa"]
    if have_ow_key:
        sources_to_run.append("openweather")
    else:
        print("(skipping openweather: OPENWEATHER_API_KEY not set)")

    for source in sources_to_run:
        stations = list_source_station_ids(conn, source)
        if not stations:
            continue
        handler = {"noaa": ingest_noaa, "openweather": ingest_openweather}[source]
        for station in stations:
            try:
                handler(conn, station)
                print(f"{source:<12} {station:<10} ingested")
            except OpenWeatherAuthError as e:
                print(f"skipping openweather: {e}")
                break

    print()
    grouped = latest_per_source(conn)
    if not grouped:
        print("(no observations)")
        return 0
    for station_id, sources in grouped.items():
        print(format_station_report(reconcile_station(station_id, sources)))
        print()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sw",
        description="StandardizeWeather: ingest weather feeds and reconcile across sources.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser(
        "run",
        help="Seed aliases, ingest every seeded source, and reconcile.",
    )
    p_run.add_argument("--seeds", default=DEFAULT_SEEDS)
    p_run.add_argument("--db", default=DEFAULT_DB)

    p_ing = sub.add_parser("ingest", help="Pull observations from one source.")
    p_ing.add_argument("source", choices=["noaa", "openweather"])
    p_ing.add_argument(
        "station",
        nargs="?",
        default=None,
        help="Source-specific station id. Omit to ingest every seeded station for this source.",
    )
    p_ing.add_argument("--db", default=DEFAULT_DB)

    p_rec = sub.add_parser("reconcile", help="Compare sources and flag breaks.")
    p_rec.add_argument("--station", default=None)
    p_rec.add_argument("--db", default=DEFAULT_DB)

    p_seed = sub.add_parser(
        "seed-aliases", help="Load station aliases from a JSON file."
    )
    p_seed.add_argument("--file", default=DEFAULT_SEEDS)
    p_seed.add_argument("--db", default=DEFAULT_DB)

    return p


HANDLERS = {
    "run": cmd_run,
    "ingest": cmd_ingest,
    "reconcile": cmd_reconcile,
    "seed-aliases": cmd_seed_aliases,
}


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    args = _build_parser().parse_args(argv)
    return HANDLERS[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
