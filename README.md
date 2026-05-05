# StandardizeWeather

[![test](https://github.com/Adenegar/StandardizeWeather/actions/workflows/test.yml/badge.svg)](https://github.com/Adenegar/StandardizeWeather/actions/workflows/test.yml)

Pulls "current conditions" from multiple weather feeds, normalizes them to one
canonical schema, and prints a side-by-side reconciliation showing where the
sources disagree.

```
$ sw demo
seeded 2 aliases from seeds/aliases.json

noaa         KBOI       ingested
openweather  5586437    ingested

=== KBOI === (2 sources)
  noaa          temp= 21.00  hum= 30.52  pres= 1010.84    observed 2026-05-05T18:35:00+00:00
  openweather   temp= 21.32  hum= 35.00  pres= 1008.00    observed 2026-05-05T18:55:22+00:00
  median        temp= 21.16  hum= 32.76  pres= 1009.42

  noaa          Δtemp=-0.16  Δhum=-2.24  Δpres=+1.42   OK
  openweather   Δtemp=+0.16  Δhum=+2.24  Δpres=-1.42   OK

  no breaks.
```

`BREAK` appears next to any source whose value falls outside the per-field
tolerance (defaults: ±1.5°C, ±10 humidity points, ±3 hPa).

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
sw demo                              # NOAA only — works immediately, no auth
```

To unlock the second source:

```bash
cp .env.example .env                 # then paste your OpenWeather API key
sw demo                              # now ingests both sources and reconciles
```

Get a free OpenWeather API key at <https://openweathermap.org/api>. New keys
take a few minutes to a couple of hours to activate.

## Other commands

```bash
sw ingest noaa                       # ingest every seeded NOAA station
sw ingest openweather                # ingest every seeded OpenWeather station
sw ingest noaa KSFO                  # one-off: ingest a specific station
sw reconcile                         # report all stations
sw reconcile --station KBOI          # report one station
sw seed-aliases --file seeds/aliases.json
```

The seed file (`seeds/aliases.json`) is the source of truth for which stations
this project tracks. Add a new station by appending an entry there.

## Why this exists

This is a portfolio project for a data-integration role. The shape mirrors a
portfolio-data ingest pipeline — many sources claim to know the same fact, we
ingest all their claims, store one canonical version, and explain
disagreements. Two practice goals shaped the work:

1. The practical side of data standardization: identity resolution, unit
   conversion, and the edge cases that only surface when several feeds need to
   agree.
2. GitHub Actions for CI, hence the workflow under `.github/workflows/`.

## Internals

```
src/standardize_weather/
  schema.py            # canonical Observation model
  db.py                # SQLite connection, migrations, insert/fetch helpers
  units.py             # unit conversions (Pa → hPa, etc.)
  stations.py          # station-alias table: source id → canonical id
  feeds/
    http.py            # retry/backoff HTTP client with secret redaction
    noaa.py            # NOAA api.weather.gov transport
    openweather.py     # OpenWeather transport (units pinned to metric)
  normalize/
    noaa.py            # NOAA payload → Observation
    openweather.py     # OpenWeather payload → Observation
  ingest.py            # orchestration: fetch → store raw → map → insert
  reconcile.py         # latest-per-source diff with break flags
  cli.py               # `sw` entrypoint
seeds/
  aliases.json         # checked-in station-alias seed data
tests/
```

### Tables

- `observations` — canonical normalized rows. `UNIQUE(source, source_record_id)`
  makes re-ingest idempotent.
- `raw_payloads` — original feed payload, keyed identically to canonical rows so
  any disagreement can be traced back to what the source actually sent.
- `station_aliases` — maps each source's station identifier to our canonical
  `station_id`. Identity resolution across sources is its own problem.

### Still to come

A third messy source over FTP, an explicit validation-rule layer, scheduling,
and a daily report file.
