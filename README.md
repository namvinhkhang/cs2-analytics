# CS2 Analytics

Warehouse-first analytics for modern Counter-Strike 2. The project ingests CS API
data, models it with dbt in Snowflake, trains an Upset Tracker model, and serves a
Streamlit dashboard for product-facing analysis.

## What It Does

The v1 product has three analytics tracks:

- **Upset Tracker:** ranks matches by model-estimated upset probability using
  CS API match and ranking features.
- **Hidden Gem Scout:** finds tier 2/3/4 players whose recent form clears
  benchmark thresholds from the tier above them.
- **Choke/Clutch Profile:** planned team pressure profile. The dashboard page is
  intentionally deferred until the underlying source data and mart are upgraded.

The dashboard currently ships Upset Tracker and Hidden Gem Scout. It reads local
Parquet snapshots of marts plus versioned ML artifacts, so page refreshes do not
query Snowflake directly.

## Architecture

```text
CS API
  -> scripts/bootstrap_csapi.py
  -> raw Parquet in S3
  -> Snowflake RAW tables
  -> dbt staging/intermediate/marts
  -> ML artifacts in ml/
  -> dashboard snapshots in dashboard/snapshots/
  -> Streamlit dashboard
```

Snowflake and dbt are the source of truth. Python scripts handle ingestion,
training, prediction explainability, and dashboard snapshot export.

## Main Directories

- `src/cs2_analytics/`: ingestion clients, typed models, config, and utilities.
- `scripts/bootstrap_csapi.py`: CS API ingestion entrypoint.
- `dbt_project/`: Snowflake models, tests, sources, and setup SQL.
- `ml/`: Upset Tracker training, prediction helpers, model card, and artifacts.
- `dashboard/`: Streamlit app, mart snapshot export command, and dashboard helpers.
- `airflow/`: local Airflow DAGs for scheduled ingestion and dbt refreshes.
- `tests/`: unit, dbt-SQL, DAG, ML, dashboard, and optional browser smoke tests.
- `tasks/`: working notes, reviews, and lessons captured during implementation.

## Requirements

- Python `>=3.12`
- `uv`
- Snowflake account and key-pair auth for warehouse/dbt work
- S3-compatible bucket credentials for raw CS API output
- Docker, if running local Airflow
- GitHub CLI, if publishing branches/PRs from the command line

## Setup

Install dependencies:

```bash
uv sync
```

Create a local `.env` file with the credentials needed by ingestion, dbt,
Snowflake, and S3:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` if using temporary AWS credentials
- `CS2_AWS_REGION`
- `CS2_AWS_S3_BUCKET`
- `CS2_FACEIT_API_KEY`
- `CS2_PANDASCORE_API_KEY`
- `CS2_LIQUIPEDIA_API_KEY` if using Liquipedia enrichment
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_PRIVATE_KEY_PATH`

dbt reads exported shell environment variables; it does not load `.env` by
itself, so export the file before running ingestion, dbt, ML, or snapshot
commands:

```bash
set -a; source .env; set +a
```

Do not commit `.env`, private keys, Snowflake credentials, or raw secrets.

Verify the local project after setup:

```bash
uv run ruff check .
uv run pytest
```

To enable automated dashboard refreshes on GitHub:

1. Open a pull request from this branch into `main`.
2. Merge it after the tests pass.
3. Add the GitHub repository secrets listed in the GitHub Actions Refresh
   section.
4. Run the `Dashboard Refresh` workflow manually with the `daily` profile.
5. Confirm the run succeeds and commits any changed files in
   `dashboard/snapshots/` and weekly ML artifact paths.
6. Deploy or refresh the Streamlit app from `main`.

## Daily Operations

Run this once per day after exporting `.env`:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_csapi.py --profile daily
uv run dbt run --select mart_upset_features mart_hidden_gems --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --select mart_upset_features mart_hidden_gems --project-dir dbt_project --profiles-dir dbt_project
uv run python -m dashboard.export_snapshots
```

The daily profile is bounded for frequent use. It refreshes current rankings,
current player profile snapshots, recent matches, and recent player stats with
small default page caps.

## Weekly Operations

Run this once per week after exporting `.env`:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_csapi.py --profile weekly
uv run dbt run --select mart_upset_features mart_hidden_gems mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --select mart_upset_features mart_hidden_gems mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project
uv run python -m ml.train
uv run python -m dashboard.export_snapshots
```

The weekly profile collects a deeper rolling window for Hidden Gem Scout and keeps
raw S3 writes resumable by skipping output objects that already exist.

## Backfills

Backfill is manual-only and requires explicit opt-in:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_csapi.py --profile backfill --allow-backfill
```

Useful controls:

- `CS2_CSAPI_BACKFILL_MATCH_OFFSET`
- `CS2_CSAPI_BACKFILL_MAX_MATCHES`
- `CS2_CSAPI_BACKFILL_MATCH_PAGES`
- `CS2_CSAPI_BACKFILL_PLAYER_STAT_MATCH_LIMIT`

Profile defaults can also be overridden globally, for example
`CS2_CSAPI_MATCH_PAGES=5`, or per profile, for example
`CS2_CSAPI_DAILY_MATCH_PAGES=2`.

## Dashboard

Export dashboard snapshots after dbt finishes:

```bash
set -a; source .env; set +a
uv run python -m dashboard.export_snapshots
```

Run Streamlit locally:

```bash
uv run streamlit run dashboard/Home.py
```

Open the URL Streamlit prints, usually:

```text
http://localhost:8501
```

The dashboard expects:

- `dashboard/snapshots/mart_upset_features.parquet`
- `dashboard/snapshots/mart_hidden_gems.parquet`
- `ml/models/upset_tracker_v1.0.joblib`
- `ml/evaluation/decision_threshold.txt`
- `ml/evaluation/metrics.json`
- `ml/MODEL_CARD.md`

## Hosting For Free

Use Streamlit Community Cloud for the simplest free deployment:

1. Push this repository to GitHub.
2. Deploy a new Streamlit app from the repo.
3. Set the entrypoint to `dashboard/Home.py`.
4. Commit dashboard snapshot Parquet files if the public app should avoid live
   Snowflake access.
5. If the app needs live Snowflake access, add credentials through Streamlit
   secrets instead of committing them.

GitHub Student Developer Pack credits can help with alternatives like
DigitalOcean or Azure, but Streamlit Community Cloud is the lowest-maintenance
fit for this app.

## GitHub Actions Refresh

The repository includes `.github/workflows/dashboard-refresh.yml` to keep hosted
dashboard snapshots fresh without running a 24/7 server.

GitHub only runs scheduled workflows from the default branch, so merge this
workflow to `main` before relying on the daily and weekly timers.

After the pull request is merged:

1. Go to GitHub repo Settings, then Secrets and variables, then Actions.
2. Add each required value as a repository secret.
3. Go to the Actions tab and select `Dashboard Refresh`.
4. Click Run workflow, choose `daily`, and run it from `main`.
5. Open the workflow logs if it fails. Missing or misspelled secrets usually
   show up during the ingest, Snowflake key, dbt, or S3 steps.
6. After the first successful daily run, let the scheduled daily and weekly
   runs take over.

You can also start the first run from the GitHub CLI:

```bash
gh workflow run dashboard-refresh.yml --ref main -f profile=daily
```

Schedules are in UTC:

- Daily refresh: `17 10 * * *`
- Weekly refresh: `43 11 * * 1`

You can also run it manually from GitHub Actions with the `daily` or `weekly`
profile. The daily run ingests recent CS API data, rebuilds/test the dashboard
marts, exports snapshots, and commits changed snapshots. The weekly run also
rebuilds `mart_choke_profile` and retrains the Upset Tracker model before
exporting snapshots.

Add these repository secrets in GitHub before enabling the workflow:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` if using temporary AWS credentials
- `CS2_AWS_REGION`
- `CS2_AWS_S3_BUCKET`
- `CS2_FACEIT_API_KEY`
- `CS2_PANDASCORE_API_KEY`
- `CS2_LIQUIPEDIA_API_KEY` if using Liquipedia enrichment
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_PRIVATE_KEY`

`SNOWFLAKE_PRIVATE_KEY` should contain the full private key text. Escaped
newlines (`\n`) and normal multi-line secret values are both handled by the
workflow.

## Airflow

Start local Airflow:

```bash
docker compose --env-file .env -f airflow/docker-compose.yml up airflow-init
docker compose --env-file .env -f airflow/docker-compose.yml up -d
```

The daily DAG runs the `daily` CS API profile. The weekly rankings DAG runs the
`weekly` profile. The `backfill` profile has no scheduled trigger by default.

## Validation

Run fast checks:

```bash
uv run ruff check .
uv run pytest
```

Run the optional browser smoke test against a local dashboard server:

```bash
uv run streamlit run dashboard/Home.py
CS2_DASHBOARD_BASE_URL=http://localhost:8501 uv run pytest tests/test_dashboard_browser.py -q
```

Run dbt validation against Snowflake:

```bash
set -a; source .env; set +a
uv run dbt run --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --project-dir dbt_project --profiles-dir dbt_project
```

## Current Limitations

- Choke/Clutch exact lead-blown, halftime comeback, bracket, and elimination
  metrics remain deferred until trustworthy round/half/bracket source data is
  ingested with aligned team identities.
- Dashboard snapshots are local files today. Refresh them after warehouse/dbt
  updates, or wire a scheduled export workflow before relying on hosted freshness.
- Upset Tracker predictions are watchlist signals, not certainties.
