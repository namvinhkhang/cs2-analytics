# CS2 Analytics

Warehouse-first CS2 analytics project for three v1 products:

- Upset Tracker from CS API-backed `mart_upset_features`
- Hidden Gem Scout from CS API player form, team rankings, and benchmark-gap trends
- Choke/Clutch Profile with explicit metric quality flags while exact round data is unavailable

## CS API Bootstrap

Run CS API ingestion profiles from the repo root after exporting environment variables from `.env`:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_csapi.py --profile daily
uv run python scripts/bootstrap_csapi.py --profile weekly
uv run python scripts/bootstrap_csapi.py --profile backfill --allow-backfill
```

Profile defaults can be overridden globally, for example `CS2_CSAPI_MATCH_PAGES=5`, or per profile, for example `CS2_CSAPI_DAILY_MATCH_PAGES=2`. Backfills require either `--allow-backfill` or `CS2_CSAPI_ALLOW_BACKFILL=true`.

Each profile checks its target raw S3 objects before making API calls. Existing ranking, match, or player-stat objects are skipped so scheduled reruns do not overwrite raw data; resume backfills by changing `CS2_CSAPI_BACKFILL_MATCH_OFFSET` and, when needed, `CS2_CSAPI_BACKFILL_MAX_MATCHES`.

## Warehouse Refresh

Run dbt against Snowflake with exported environment variables:

```bash
set -a; source .env; set +a
uv run dbt run --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --project-dir dbt_project --profiles-dir dbt_project
```

For targeted v1 marts:

```bash
uv run dbt run --select mart_upset_features mart_hidden_gems mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --select mart_upset_features mart_hidden_gems mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project
```

## ML Training

Retrain the Upset Tracker model from Snowflake:

```bash
set -a; source .env; set +a
uv run python -m ml.train
```

The current model contract uses only pre-match features: `ranking_delta`, `is_cross_region`, `team_a_ranking`, and `team_b_ranking`.

## Airflow

The local Airflow stack mounts `src/`, `scripts/`, and `airflow/dags/` for development:

```bash
docker compose --env-file .env -f airflow/docker-compose.yml up airflow-init
docker compose --env-file .env -f airflow/docker-compose.yml up -d
```

The daily DAG runs the bounded CS API `daily` profile. The weekly rankings DAG runs the deeper CS API `weekly` profile. The `backfill` profile is manual only.

## Dashboard

The Streamlit dashboard is planned in `.planning/FUTURE_WORK_PLAN.md`. The first implementation slice should read cached mart snapshots plus versioned ML artifacts instead of querying Snowflake on every page refresh.
