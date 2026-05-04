# weather-truth

A daily pipeline that ingests "current conditions" weather data from multiple
sources (NOAA, OpenWeather, WeatherAPI, a local PWS feed over FTP), normalizes
them to one canonical schema, validates, and reconciles disagreements — surfacing
breaks in a daily report.

The shape of the project mirrors a portfolio-data ingest pipeline: many sources
claim to know the same fact; we ingest all their claims, store one canonical
version, and explain disagreements.

## Status

Milestone 1: canonical schema + SQLite storage. See `PLAN.md` for the full roadmap.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Layout

```
src/weather_truth/
  schema.py    # canonical Observation model — every feed is mapped into this
  db.py        # SQLite connection + migrations + insert/fetch helpers
tests/
```

## Tables

- `observations` — canonical normalized rows.
- `raw_payloads` — original blob keyed by `(source, source_record_id)` so a break
  can always be traced back to what the feed actually said.
- `station_aliases` — maps each source's station identifier to our canonical
  `station_id`. Identity resolution across sources is its own problem.
