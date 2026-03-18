# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install / sync dependencies (always use uv)
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_config.py

# Run a single test by name
uv run pytest tests/test_config.py::TestSettings::test_settings_reads_env_vars

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/cs2_analytics/

# Format
uv run ruff format src/ tests/
```

## Architecture

Full-stack ELT pipeline for CS2 professional esports analytics. Data flows:
**APIs → Parquet → S3 → Airflow DAGs → Snowflake → dbt models → Streamlit dashboard**

### Source Layout

```
src/cs2_analytics/
├── models/           # Pydantic v2 data contracts
│   ├── canonical.py  # Match, Player, Team — shared schema written to Parquet
│   ├── faceit.py     # FACEITMatch, FACEITPlayer (source-specific, extra="ignore")
│   ├── liquipedia.py # LiquipediaTeam/Player/Match/Tournament/Placement
│   └── pandascore.py # PandaScoreMatch, PandaScorePlayer
├── ingestion/
│   ├── base.py       # BaseAPIClient: httpx + tenacity retries + asyncio.Semaphore rate limiting
│   ├── faceit.py     # FACEIT API client (best per-match stats: ADR, KAST, kills)
│   ├── liquipedia.py # Liquipedia API v3 (tournament metadata, rosters, placements)
│   ├── pandascore.py # PandaScore API (tier-1 pro match results)
│   └── kaggle.py     # One-time historical CSV bootstrap loader
└── utils/
    ├── config.py     # Settings(BaseSettings) — all config via CS2_* env vars
    ├── parquet.py    # Serialize canonical models to Parquet via pyarrow
    └── s3.py         # Upload Parquet files to S3 (raw/ prefix, date-partitioned)
```

### Model Pattern (Critical)

- **Canonical models** (`canonical.py`): `extra="forbid"` — strict schema, written to Parquet by every client
- **Source models** (per-API files): `extra="ignore"` — tolerant of API schema drift
- Every source model has a `to_canonical()` method returning the appropriate canonical type
- No Pydantic v1 `class Config` — always use `model_config = ConfigDict(...)`

### Config Pattern

All settings come from environment variables with `CS2_` prefix (e.g., `CS2_FACEIT_API_KEY`). Copy `.env.example` to `.env` to run locally. Required vars: `CS2_FACEIT_API_KEY`, `CS2_PANDASCORE_API_KEY`, `CS2_LIQUIPEDIA_API_KEY`, `CS2_AWS_S3_BUCKET`, `CS2_KAGGLE_USERNAME`, `CS2_KAGGLE_KEY`. Airflow vars: `CS2_AIRFLOW_FERNET_KEY`, `CS2_AIRFLOW_SECRET_KEY`, `CS2_SLACK_WEBHOOK_URL`. Optional: `CS2_AWS_REGION` (defaults to `us-east-1`).

### BaseAPIClient

All ingestion clients extend `BaseAPIClient` from `ingestion/base.py`. It provides:
- `async get(path, **params)` — rate-limited GET with tenacity retry (5 attempts, exponential backoff, retries on 429 and 5xx)
- `async paginate(path, ...)` — async generator yielding pages
- Class-level `_semaphore` for per-source concurrency control (all instances of the same client share one semaphore)
- Async context manager (`async with client:`)

### Airflow DAGs

```
airflow/
├── Dockerfile              # Extends apache/airflow:2.9.3-python3.12, bakes in cs2_analytics + Slack provider
├── docker-compose.yml      # CeleryExecutor stack: webserver, scheduler, worker, triggerer, postgres, redis
└── dags/
    ├── cs2_daily_matches.py    # Every 6h — FACEIT + PandaScore match ingestion with S3 idempotency
    ├── cs2_weekly_rankings.py  # @weekly — Liquipedia team/player rankings
    ├── cs2_tournament_sync.py  # @daily — Liquipedia tournament match sync
    ├── fail_intentionally.py   # Dev DAG — smoke-test Slack webhook
    └── utils/
        └── slack_alerts.py     # on_failure_callback — shared Slack webhook alerting
```

**Docker stack:** `docker compose --env-file .env -f airflow/docker-compose.yml build && docker compose --env-file .env -f airflow/docker-compose.yml run --rm airflow-init && docker compose --env-file .env -f airflow/docker-compose.yml up -d`
**Airflow UI:** http://localhost:8080 (admin/admin)
**Key:** Dockerfile must `pip install` as `airflow` user (not root) — official image blocks root pip.

### Project Phases

| Phase | Status | Directory |
|-------|--------|-----------|
| 1 — Data Ingestion | Complete | `src/cs2_analytics/` |
| 2 — Orchestration | Complete (verified) | `airflow/dags/` |
| 3 — dbt + Snowflake Warehouse | Not Started | `dbt_project/` |
| 4 — Analytics Products | Not Started | `dashboard/`, `ml/` |
| 5 — Dashboard & Deployment | Not Started | `dashboard/` |
| 6 — CI & Polish | Not Started | `.github/workflows/` |

Planning docs are in `.planning/` (GSD workflow). Phase plans are in `.planning/phases/`.
170 tests across Phase 1 (158) and Phase 2 (12).

## Key Decisions

- **No HLTV scraping** — Cloudflare-protected, ToS risk. Use Kaggle CSV for historical bootstrap instead.
- **FACEIT is primary stats source** — only official API with per-match ADR/KAST at semi-pro level.
- **Snowflake over BigQuery** — better Airflow/dbt ecosystem docs; $400 free trial credit.
- **AWS S3 over GCS** — higher frequency in intern job postings; 5 GB free tier.
- Tests use `respx` for mocking httpx requests — never mock at the boto3 or requests level.
- `asyncio_mode = "auto"` in pytest — all async tests run without `@pytest.mark.asyncio`.
- **Airflow Dockerfile:** must `pip install` as `USER airflow`, not root — official image blocks root pip. Use `COPY --chown=airflow:0` for files.
- **docker-compose.yml:** do not use `version:` key — modern Compose ignores it and warns.
- **DagBag testing:** use `dagbag.dags.get()` not `dagbag.get_dag()` — the latter crashes on uninitialized SQLite.
- **Docker Compose `--env-file`:** Always use `--env-file .env` with `-f airflow/docker-compose.yml` — Compose doesn't auto-discover `.env` from project root when using `-f` with a subdirectory path.
- **DAG imports:** Use `from utils.slack_alerts import ...` (not `from airflow.dags.utils...`) — Airflow adds dags folder to sys.path automatically; `airflow.dags` is not a Python package.
- **Settings `extra="ignore"`:** Required because `.env` contains non-Settings CS2_* vars (Airflow, Slack) that would fail pydantic validation.
- **Celery provider:** Must install `apache-airflow-providers-celery` in Dockerfile — not included in base image but required for CeleryExecutor.
- **AWS credentials:** Use `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (no `CS2_` prefix) — boto3 reads these directly from env.
- **Config tests:** Pass `_env_file=None` when constructing `Settings()` in tests to prevent real `.env` from leaking into test assertions.
- **docker-compose YAML `environment:` merging:** YAML anchor `<<:` merge replaces entire keys, not extends them. A service-level `environment:` block fully replaces the common anchor's `environment:` — never add a service-level `environment:` override on top of `<<: *airflow-common`. Put all shared env vars (including `DUMB_INIT_SETSID`) in the common block.
- **Scheduler healthcheck CMD vs CMD-SHELL:** Docker Compose `healthcheck.test: ["CMD", ...]` does NOT invoke a shell, so `$${HOSTNAME}` is passed literally. Use `["CMD-SHELL", "... $$HOSTNAME"]` — `$$` escapes to a literal `$` at compose-parse time, then the shell expands `$HOSTNAME` at container runtime.
- **SlackWebhookHook API in providers-slack>=8.x:** `SlackWebhookHook(webhook_url=...)` was removed — the hook now requires `slack_webhook_conn_id` (an Airflow Connection). Since this project avoids Airflow Connections, send Slack alerts via `requests.post(webhook_url, json={"text": message})` directly.
