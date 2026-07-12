# Transit Pulse — NYC MTA Analytics Platform

## What this project is

An end-to-end ELT pipeline that ingests NYC MTA subway performance data into BigQuery,
transforms it with dbt, validates it with Great Expectations, and serves it through a
Streamlit dashboard with interactive Folium maps. Orchestrated by Airflow, CI/CD via
GitHub Actions.

This is a portfolio project for a new-grad Data Engineering / Data Analyst resume.
Every decision should optimize for: (1) actually working end-to-end, (2) being
impressive when a recruiter clicks the GitHub link, (3) being defensible in a
30-minute technical interview.

## Architecture

```
MTA Open Data API (SODA, data.ny.gov)
        │
        ▼
  Python Ingestion Script
  (requests + pandas, config-driven multi-dataset)
        │
        ▼
  Google BigQuery ───── Great Expectations
  (raw layer)           (data quality tests)
        │
        ▼
  dbt Transformations
  (staging → marts)
        │
        ▼
  Streamlit + Folium
  (public dashboard)

  Orchestration: Airflow (local Docker)
  CI/CD: GitHub Actions
```

## Data sources (VERIFIED 2026-07-12 — do not use IDs from older drafts)

> ⚠️ The old "MTA Service Delivery" dataset (`nb36-cmmq`) and station dataset
> (`kk4q-3rt2`) NO LONGER EXIST. MTA split performance reporting into per-metric
> datasets. The IDs below were verified live against data.ny.gov.

All endpoints follow `https://data.ny.gov/resource/<ID>.json` (SODA API: `$where`,
`$limit`, `$offset`, `$order`; free, app token optional but raises rate limits —
register at https://data.ny.gov/signup, store as `MTA_APP_TOKEN` in `.env`).

| Dataset | ID | Grain | Key columns |
|---|---|---|---|
| Terminal On-Time Performance (2015+) | `f6rf-2a3t` | month × line × day_type | terminal_on_time_performance (0–1 fraction) |
| Customer Journey-Focused Metrics (2015+) | `r7qk-6tcy` | month × line × period | customer_journey_time, additional_platform_time, num_passengers |
| Trains Delayed (2020+) | `9zbp-wz3y` | month × line × day_type × reporting_category | delays |
| Wait Assessment (2015+) | `s666-h6b7` | month × line × day_type × period | wait_assessment |
| Mean Distance Between Failures (2015+) | `e2qc-xgxs` | month × car_class (NOT line) | mdbf, _12_month_average_mdbf |
| Subway Stations (dimension) | `39hk-dx4f` | station | stop_name, borough, daytime_routes, gtfs_latitude/longitude, ada |
| Station Monthly Ridership (2017+) | `ak4z-sape` | month × station_complex | ridership, latitude/longitude |

Notes discovered during verification:
- `month` is a Socrata `calendar_date` (`2015-01-01T00:00:00.000`) — cast to DATE.
- Percent-like metrics (OTP, wait assessment, CJT) are **0–1 fractions**, not 0–100.
- MDBF is reported by **car class**, not line — treat it as fleet-level reliability;
  join to lines only via division (A/B) if needed.
- `e2qc-xgxs.mdbf` is typed `text` in Socrata metadata — coerce to numeric on ingest.
- Station→line mapping comes from `daytime_routes` (space-separated route letters) in
  the stations dataset; split it to map stations onto lines for the Folium map.

Backup if SODA has issues: download CSVs from data.ny.gov; the ingestion script
supports `--source local --file <path>`.

## Repo structure

```
transit-pulse/
├── CLAUDE.md
├── README.md
├── .github/workflows/ci.yml
├── airflow/
│   ├── dags/transit_elt_dag.py
│   └── docker-compose.yml
├── ingestion/
│   ├── config.py          ← dataset registry (IDs, schemas, keys) — single source of truth
│   └── mta_ingest.py      ← generic SODA→BigQuery loader, driven by the registry
├── dbt_transit/
│   ├── dbt_project.yml
│   ├── profiles.yml       ← reads env vars, no hardcoded creds
│   ├── models/
│   │   ├── staging/       ← stg_terminal_otp, stg_customer_journey, stg_trains_delayed,
│   │   │                    stg_wait_assessment, stg_mdbf, stg_stations, stg_station_ridership
│   │   └── marts/         ← mart_delay_analysis, mart_station_performance,
│   │                        mart_time_trends, mart_line_reliability
│   ├── tests/assert_valid_otp_fraction.sql
│   └── macros/
├── great_expectations/
├── dashboard/
│   ├── app.py
│   └── pages/             ← 01_line_performance, 02_station_delays, 03_time_trends
├── scripts/setup_bigquery.py
├── tests/                 ← pytest unit tests (no network, no BQ)
├── requirements.txt
└── .env.example
```

## Ingestion design

`ingestion/config.py` holds a `DATASETS` registry: Socrata ID, target raw table,
explicit BigQuery schema, natural-key columns, and incremental date column per
dataset. `ingestion/mta_ingest.py` is a single generic loader:

1. Paginate SODA API (1000 rows/request, `$order` for stable paging) until exhausted
2. 3 retries with exponential backoff on HTTP errors
3. Incremental: query `MAX(month)` in BQ, fetch only newer months (`$where`);
   stations dimension is full-refresh (`WRITE_TRUNCATE`)
4. Deduplicate on the dataset's natural key before load
5. Load via `google-cloud-bigquery` with explicit schema (no autodetect), `WRITE_APPEND`
6. Add `_loaded_at TIMESTAMP` metadata column
7. Log stats: fetched / loaded / skipped as duplicates

Env vars (via `.env` + python-dotenv): `GCP_PROJECT_ID`, `BQ_DATASET_RAW`,
`GOOGLE_APPLICATION_CREDENTIALS`, `MTA_APP_TOKEN` (optional).

BigQuery free tier (10 GB storage, 1 TB queries/month) is plenty — all datasets
combined are well under 1 GB.

## dbt layer

- staging: views, one per raw table — cast types, rename, dedupe with ROW_NUMBER(),
  add period_month/period_year, convert 0–1 fractions to percentages where useful
- marts: tables
  - `mart_delay_analysis` — delays by line/month, rolling 3-mo avg, MoM % change, severity rank
  - `mart_station_performance` — line OTP joined to stations via daytime_routes +
    station ridership; reliability tiers: reliable >90%, at risk 80–90%, poor <80%
  - `mart_time_trends` — peak vs offpeak (from customer journey `period` column),
    weekday vs weekend (from `day_type` 1/2), monthly heatmap feed
  - `mart_line_reliability` — composite line health score from OTP + wait assessment +
    CJT, ridership-weighted; fleet MDBF trend as context
- tests: not_null + unique on keys, accepted_values on line, custom
  `assert_valid_otp_fraction` (0 ≤ otp ≤ 1 in staging), relationships staging↔marts
- `dbt docs generate` → lineage graph screenshot in README

## Data quality (Great Expectations)

Suite on raw tables, runs AFTER ingestion, BEFORE dbt in the DAG; failure stops the DAG:
- not_null: month, line, terminal_on_time_performance
- terminal_on_time_performance between 0 and 1 (fractions!)
- ridership between 0 and 10,000,000
- line in known MTA line set (1,2,3,4,5,6,7,A,B,C,D,E,F,G,J,L,M,N,Q,R,W,S lines + "Systemwide")
- table row count sanity bounds
- _loaded_at > month

## Airflow

DAG `transit_pulse_elt`, `@daily`, catchup=False, skips when no new month available.
ingest → validate (GE) → dbt run → dbt test. Each task: retries=2,
retry_delay=5min, alerting configured in default_args. Official Airflow 2.7+
Docker Compose (slim), `AIRFLOW__CORE__LOAD_EXAMPLES=false`, mount dags/ingestion/dbt.

## Dashboard (Streamlit)

Multi-page app; global sidebar (line multiselect, date range, About). Plotly charts,
`@st.cache_data(ttl=3600)` on every BQ query, must load <5s.
- Page 1 line performance: KPI cards, horizontal OTP bar chart, OTP trend lines
- Page 2 station map (VISUAL CENTERPIECE): Folium, NYC center (40.7128, -74.0060,
  zoom 11), CircleMarkers colored by line OTP tier (green/yellow/red), sized by
  station ridership, popups, per-line layer control, MarkerCluster if crowded
- Page 3 time trends: OTP heatmap (line × month), rolling 3-mo trend, YoY compare,
  best/worst month callouts
Deploy: Streamlit Community Cloud, BQ service account via Streamlit secrets.

## CI/CD

`.github/workflows/ci.yml`: ruff check + pytest on push/PR; dbt deps + dbt compile
(compile-only — no BQ creds in CI). CI badge at top of README.

## Constraints and rules

- Free tier only (BigQuery sandbox, Streamlit Community Cloud, GH Actions free minutes)
- No hardcoded credentials — env vars / `.env` (gitignored) only
- Type hints everywhere; docstrings on every function/class
- ruff for linting; no print statements — use `logging`
- Every SQL model gets at least one dbt test
- Conventional commits

## Build order (do not skip ahead)

1. ✅ Scaffold repo, venv, requirements
2. ✅ Ingestion script written; SODA endpoints verified live — **needs GCP creds to load**
3. Great Expectations suite
4. dbt staging models → `dbt run`
5. dbt marts → `dbt run` + `dbt test`
6. Streamlit dashboard page by page
7. Folium map polish
8. Airflow DAG
9. Full DAG test via Docker Compose
10. GitHub Actions CI
11. Deploy Streamlit Cloud
12. README with screenshots + architecture diagram
13. Final end-to-end polish
