# StandardizeWeather

A daily pipeline that ingests "current conditions" weather data from multiple
sources (NOAA, OpenWeather, WeatherAPI, a local PWS feed over FTP), normalizes
them to one canonical schema, validates, and reconciles disagreements — surfacing
breaks in a daily report.

The shape of the project mirrors a portfolio-data ingest pipeline: many sources
claim to know the same fact; we ingest all their claims, store one canonical
version, and explain disagreements. Weather is the vehicle here — part of my
goal in building this was to get hands-on with the practical side of data
standardization: identity resolution, unit conversion, and the edge cases that
only show up once you try to make several feeds agree.

## What works today

- Canonical `Observation` schema and SQLite storage with idempotent inserts.
- NOAA `api.weather.gov` ingest, end-to-end (live).
- OpenWeather ingest, end-to-end, with a JSON-seeded station-alias table that
  resolves each source's identifier to a single canonical station id.
- Retry-with-backoff HTTP client; secrets in URLs are redacted from error output.
- Test suite covering mappers, HTTP retries, and end-to-end ingest with mocked
  transports — no live network calls during tests.

Still to come: a third messy source over FTP, a validation-rule layer, the
reconciliation engine that compares sources, scheduling, and a daily report.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # then add your OPENWEATHER_API_KEY
pytest
```

## Usage

```bash
# Seed station aliases (maps OpenWeather city ids to canonical station ids)
python -m standardize_weather.ingest seed-aliases --file seeds/aliases.json --db wt.db

# Pull a single observation from each source
python -m standardize_weather.ingest noaa --station KBOI --db wt.db
python -m standardize_weather.ingest openweather --station 5586437 --db wt.db

sqlite3 -header -column wt.db \
  "SELECT source, station_id, observed_at, temp_c, pressure_hpa FROM observations;"
```

## Layout

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
  ingest.py            # CLI: noaa | openweather | seed-aliases
seeds/
  aliases.json         # checked-in station-alias seed data
tests/
```

## Tables

- `observations` — canonical normalized rows. `UNIQUE(source, source_record_id)`
  makes re-ingest idempotent.
- `raw_payloads` — original feed payload, keyed identically to canonical rows so
  any disagreement can be traced back to what the source actually sent.
- `station_aliases` — maps each source's station identifier to our canonical
  `station_id`. Identity resolution across sources is its own problem.
