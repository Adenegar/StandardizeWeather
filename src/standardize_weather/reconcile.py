from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from statistics import median

# Generous defaults — meant to catch unit errors and stale feeds, not to
# bicker about a couple tenths of a degree.
DEFAULT_TOLERANCES: dict[str, float] = {
    "temp_c": 1.5,
    "humidity_pct": 10.0,
    "pressure_hpa": 3.0,
}

NUMERIC_FIELDS = ("temp_c", "humidity_pct", "pressure_hpa")


@dataclass(frozen=True)
class SourceObs:
    source: str
    observed_at: str
    temp_c: float | None
    humidity_pct: float | None
    pressure_hpa: float | None


@dataclass(frozen=True)
class FieldDelta:
    field: str
    value: float | None
    median: float | None
    delta: float | None
    is_break: bool


@dataclass
class StationReport:
    station_id: str
    sources: list[SourceObs]
    medians: dict[str, float | None] = field(default_factory=dict)
    deltas: dict[str, list[FieldDelta]] = field(default_factory=dict)

    @property
    def has_breaks(self) -> bool:
        return any(d.is_break for ds in self.deltas.values() for d in ds)


def latest_per_source(
    conn: sqlite3.Connection, station_id: str | None = None
) -> dict[str, list[SourceObs]]:
    """Return {station_id: [SourceObs ...]}, taking each source's most-recent
    observation per station (by `observed_at`)."""
    sql = """
        SELECT station_id, source, observed_at, temp_c, humidity_pct, pressure_hpa
        FROM observations o
        WHERE observed_at = (
            SELECT MAX(observed_at) FROM observations
            WHERE source = o.source AND station_id = o.station_id
        )
    """
    params: tuple = ()
    if station_id is not None:
        sql += " AND station_id = ?"
        params = (station_id,)
    sql += " ORDER BY station_id, source"

    out: dict[str, list[SourceObs]] = {}
    for r in conn.execute(sql, params).fetchall():
        out.setdefault(r["station_id"], []).append(
            SourceObs(
                source=r["source"],
                observed_at=r["observed_at"],
                temp_c=r["temp_c"],
                humidity_pct=r["humidity_pct"],
                pressure_hpa=r["pressure_hpa"],
            )
        )
    return out


def reconcile_station(
    station_id: str,
    sources: list[SourceObs],
    tolerances: dict[str, float] = DEFAULT_TOLERANCES,
) -> StationReport:
    medians: dict[str, float | None] = {}
    for fname in NUMERIC_FIELDS:
        values = [getattr(s, fname) for s in sources if getattr(s, fname) is not None]
        medians[fname] = median(values) if values else None

    deltas: dict[str, list[FieldDelta]] = {}
    for src in sources:
        src_deltas: list[FieldDelta] = []
        for fname in NUMERIC_FIELDS:
            v = getattr(src, fname)
            m = medians[fname]
            if v is None or m is None:
                src_deltas.append(FieldDelta(fname, v, m, None, False))
                continue
            d = v - m
            tol = tolerances.get(fname, float("inf"))
            src_deltas.append(FieldDelta(fname, v, m, d, abs(d) > tol))
        deltas[src.source] = src_deltas

    return StationReport(
        station_id=station_id,
        sources=sources,
        medians=medians,
        deltas=deltas,
    )


def _short(name: str) -> str:
    return {"temp_c": "temp", "humidity_pct": "hum", "pressure_hpa": "pres"}.get(name, name)


def _fmt(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else "--"


def format_station_report(report: StationReport) -> str:
    n = len(report.sources)
    lines = [f"=== {report.station_id} === ({n} source{'s' if n != 1 else ''})"]
    for s in report.sources:
        lines.append(
            f"  {s.source:<13} "
            f"temp={_fmt(s.temp_c):>6}  "
            f"hum={_fmt(s.humidity_pct):>6}  "
            f"pres={_fmt(s.pressure_hpa):>8}    "
            f"observed {s.observed_at}"
        )

    if n < 2:
        if n == 1:
            lines.append("  (only one source — nothing to reconcile)")
        return "\n".join(lines)

    lines.append(
        f"  {'median':<13} "
        f"temp={_fmt(report.medians['temp_c']):>6}  "
        f"hum={_fmt(report.medians['humidity_pct']):>6}  "
        f"pres={_fmt(report.medians['pressure_hpa']):>8}"
    )
    lines.append("")

    for src_name, ds in report.deltas.items():
        parts = []
        flagged = []
        for d in ds:
            label = _short(d.field)
            if d.delta is None:
                parts.append(f"Δ{label}=--")
            else:
                parts.append(f"Δ{label}={d.delta:+.2f}")
            if d.is_break:
                flagged.append(d.field)
        marker = "BREAK " + ", ".join(flagged) if flagged else "OK"
        lines.append(f"  {src_name:<13} {'  '.join(parts)}   {marker}")

    if not report.has_breaks:
        lines.append("")
        lines.append("  no breaks.")
    return "\n".join(lines)


