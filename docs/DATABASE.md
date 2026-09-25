# CityPulse: Database

## Why SQLite (and how to switch)

CityPulse uses **SQLite**: a single file (`backend/data/citypulse.db`), no server, no setup. That is the
right trade-off for a 24-hour hackathon. All access goes through **SQLAlchemy** (a Python library
that turns Python classes into SQL), so moving to PostgreSQL is a configuration change:

```bash
pip install "psycopg[binary]"
export CITYPULSE_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/citypulse
```

SQLite runs in **WAL mode** ("write-ahead log"), which lets the API read while the pipeline writes.

## The database is not on the critical path

The live analysis reads from an **in-memory rolling store** (last 40 minutes). The database keeps:

- **history**: 3 days of synthetic data used to learn baselines, plus the recorded storm for replay,
- **live readings and reports**: for inspection and audit,
- **alerts**, **zone status snapshots** and the **simulation log**.

Every database call is best-effort (`services/persistence.py`). If the database fails, the live
pulse keeps running, `/api/health` shows `storage: degraded`, and default baselines are used if
history can't be loaded. This is tested in `test_resilience.py::test_database_outage_keeps_live_pulse_running`.

## Tables

Defined in `backend/app/database.py`.

### `zones`
| Column | Type | Notes |
|---|---|---|
| `id` | varchar PK | block ID `C2-9` (district + keypad block; 225 blocks) |
| `number` | int | |
| `name`, `short_name` | varchar | "Walled City (C2-9)", "Walled City" |
| `boundary` | JSON | GeoJSON square (~1.5 km) |

### `civic_readings`: the common data model for measurements
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `source`, `source_type` | varchar | feed id, e.g. `weather` |
| `provider` | varchar | `synthetic city model`, `Open-Meteo (public API)`, `synthetic history`, `recorded archive (1-min)` |
| `zone_id` | varchar | |
| `ts` | datetime (UTC) | when it was observed |
| `ingested_at` | datetime (UTC) | when CityPulse received it |
| `metric`, `value`, `unit` | | canonical units (mm/h, °C, km/h, %, min, µg/m³, AQI, cm) |
| `confidence` | float | 0-1 |
| `data_status` | varchar | `live`, `simulated`, `fallback` |
| `sensor_id` | varchar, nullable | e.g. `RG-E-01` |
| `is_history` | bool | `true` = seeded history / archive |
| `metadata` | JSON | e.g. bus `route_id` |

Index: `ix_readings_zone_metric_ts (zone_id, metric, ts)`: every baseline and replay query filters
by zone, metric and time range.

### `incidents`: anonymous civic reports
| Column | Type | Notes |
|---|---|---|
| `id` | varchar PK | upstream request id (`SR-…`), used to ignore duplicates |
| `source`, `zone_id` | varchar | |
| `ts`, `ingested_at` | datetime (UTC) | |
| `category` | varchar | `waterlogging`, `pothole`, `power_outage`, … |
| `severity` | varchar | `low`, `moderate`, `high` |
| `lat`, `lon` | float | rounded to ~10 m |
| `data_status`, `is_history` | | |
| `metadata` | JSON | only `personal_fields_dropped` (a count) |

There is deliberately **no column for names, phone numbers, account IDs or free text**.
Index: `ix_incidents_zone_ts (zone_id, ts)`.

### `alerts`: monitoring-agent alerts
| Column | Notes |
|---|---|
| `id` | int PK |
| `key` | de-duplication key, e.g. `C2-9:disruption` (indexed) |
| `zone_id`, `level`, `kind`, `title` | |
| `observed` | JSON list, measured facts |
| `possible_relationship` | text, hedged link, may be null |
| `causation_note` | text, always "Not a confirmed cause…" |
| `opened_at`, `updated_at`, `resolved_at` | |

Keeping *observed*, *possible relationship* and *causation note* in separate columns makes the
epistemic separation part of the data model, not just the UI.

### `zone_snapshots`
Zone status every 15 seconds (`ts`, `zone_id`, `status`, `anomalies` JSON, `relationships` JSON).
Index on `ts`. Powers the heat-map timeline and gives an audit trail of what the system flagged.

### `simulation_events`
Log of demo actions (`at`, `event_type`, `zone_id`, `params`): so a demo can be reconstructed.

## Why there are no `anomalies` / `correlations` tables

Anomalies and relationships are **derived data**: they are recomputed from readings every tick
by a deterministic engine. Storing them separately would create two sources of truth. Their
history is kept compactly in `zone_snapshots`, and historical replay can recompute them exactly.

## Seed data

On start-up `Persistence.ensure_history()`:

1. creates tables (`Base.metadata.create_all`) and (re)writes the 225 blocks if the layout changed,
2. checks the history: if it's missing, older than a day, lacks the replay archive, or was made
   for a different area layout, it regenerates it (≈ 25 s, once; later starts reuse it):
   - every **10 minutes for 3 days**: all metrics for all 225 blocks (~875k rows, baseline learning),
   - every **1 minute** around the recorded storm (replay only, excluded from baselines),
   - anonymous reports drawn from the same city model,
3. clears live rows from any previous run (each run starts a fresh live session).

Typical size: ≈ 44 000 history readings (5 400 of them archive rows), ≈ 4 800 history reports,
about 11 MB on disk.

Live readings older than 6 hours are pruned automatically.

## Migrations

The schema is created with `create_all`, which is enough for a hackathon (the app owns the
database and can recreate it). For a long-lived deployment, add **Alembic** (SQLAlchemy's
migration tool): `alembic init`, point `env.py` at `app.database.Base.metadata`, and generate
the first revision with `alembic revision --autogenerate`.

## Handy queries

```bash
sqlite3 backend/data/citypulse.db
```

```sql
-- What did the agent flag?
SELECT opened_at, level, title, resolved_at FROM alerts ORDER BY opened_at DESC LIMIT 10;

-- Walled City (C2-9) rainfall over the last few minutes
SELECT ts, value FROM civic_readings
WHERE zone_id = 'C2-9' AND metric = 'rain_mm_h' AND is_history = 0 ORDER BY ts DESC LIMIT 20;

-- Reports by category in the recorded storm
SELECT category, COUNT(*) FROM incidents
WHERE is_history = 1 AND zone_id = 'C3-8' GROUP BY category ORDER BY 2 DESC;
```

To start completely fresh: stop the backend, delete `backend/data/citypulse.db`, start again.
