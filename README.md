# Transit Pulse 🚇

![CI](https://github.com/anoopibrampur/transit-pulse/actions/workflows/ci.yml/badge.svg)

End-to-end ELT pipeline for NYC MTA subway performance data: Python ingestion from the
NY Open Data SODA API into BigQuery, dbt transformations (staging → marts), Great
Expectations data-quality gates, Airflow orchestration, and a public Streamlit
dashboard with interactive Folium maps.

> 🚧 Work in progress — build order and full spec live in [CLAUDE.md](CLAUDE.md).

## Data sources

Seven MTA datasets from [data.ny.gov](https://data.ny.gov) (verified July 2026):
terminal on-time performance, customer journey metrics, trains delayed, wait
assessment, mean distance between failures, station dimension, and station monthly
ridership. See `ingestion/config.py` for the full registry with schemas.

## Getting started

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in GCP project + service-account key path
python scripts/setup_bigquery.py
python -m ingestion.mta_ingest --dry-run     # smoke test, no BQ needed
python -m ingestion.mta_ingest               # full load
```

GCP setup: create a free project, enable the BigQuery API, create a service account
with the BigQuery Admin role, download its JSON key, and point
`GOOGLE_APPLICATION_CREDENTIALS` at it in `.env`.
