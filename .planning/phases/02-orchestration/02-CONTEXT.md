# Phase 2: Orchestration - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers a fully automated, monitored, and locally reproducible pipeline orchestration layer. This includes a Dockerized Airflow stack (webserver + scheduler + CeleryExecutor workers + Postgres + Redis), three Airflow DAGs that schedule all Phase 1 ingestion clients on their respective cadences, Slack webhook failure alerting, and pytest coverage for DAG structure and task logic.

</domain>

<decisions>
## Implementation Decisions

### Docker Compose Stack
- Use `apache/airflow:2.9-python3.12` official image — matches Python 3.12 constraint
- CeleryExecutor + Redis broker — more prod-realistic stack, Redis broker explicitly required by ORC-05
- API secrets via `env_file: .env` — reuses existing `CS2_*` env var pattern, no extra secrets infra
- Healthchecks on webserver `:8080/health` — prevent startup race conditions

### DAG Design
- TaskFlow API (`@task` decorator) — modern Python-native style, cleaner than classic PythonOperator
- Call async Phase 1 clients via `asyncio.run()` wrapper — direct reuse, no duplication
- S3 key existence check before ingesting — skip if today's Parquet already exists (stateless idempotency)
- Read config from `CS2_*` env vars at task runtime — consistent with established pattern, no Airflow Connections/Variables overhead

### Failure Alerting
- Slack webhook for failure notifications — no SMTP config needed, widely adopted in data engineering
- DAG-level `on_failure_callback` — catches any task failure without per-task boilerplate
- Alert content includes: DAG name, task ID, run_id, log URL — sufficient to diagnose without opening Airflow UI
- `fail_intentionally` dev DAG included to verify Slack webhook is live before relying on it

### Development & Testing
- `pytest` + `dag.test()` for DAG structural and task-level tests
- Full type hints throughout DAG files — project standard established in Phase 1
- `structlog` for logging in DAG tasks — consistent with Phase 1 ingestion clients
- Manual first-run trigger via `airflow dags trigger` (documented in README) — avoids confusing backfill on fresh setup

### Claude's Discretion
- DAG file organization within `airflow/dags/` (one file per DAG vs shared utils module)
- Exact Postgres and Redis versions in docker-compose.yml
- Airflow webserver port mapping (default 8080)
- Volume mount strategy for DAGs directory

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/cs2_analytics/ingestion/faceit.py` — `FACEITClient` async context manager, call via `asyncio.run()`
- `src/cs2_analytics/ingestion/liquipedia.py` — `LiquipediaClient` async context manager
- `src/cs2_analytics/ingestion/pandascore.py` — `PandaScoreClient` async context manager
- `src/cs2_analytics/ingestion/kaggle.py` — `KaggleClient` (sync, one-time bootstrap — not scheduled)
- `src/cs2_analytics/utils/config.py` — `Settings(BaseSettings)` reads all `CS2_*` env vars
- `src/cs2_analytics/utils/s3.py` — `write_parquet_to_s3(bucket, key, data)` for S3 key existence check pattern

### Established Patterns
- All config via `CS2_*` env vars, loaded by `Settings()` singleton
- `structlog` for structured logging throughout ingestion layer
- `asyncio.Semaphore` for rate limiting (1 req/s FACEIT, 3.6s PandaScore, 2.0s Liquipedia)
- `tenacity` retry with exponential backoff on 429 and 5xx responses
- `uv sync` for dependency management — new Airflow deps go in `pyproject.toml`

### Integration Points
- DAGs import from `src/cs2_analytics/` — Python path must include project root in Airflow worker containers
- `CS2_*` env vars must be injected into all Airflow containers via `env_file: .env`
- New `airflow/dags/` directory is the DAG folder (set via `AIRFLOW__CORE__DAGS_FOLDER`)
- `pyproject.toml` needs `apache-airflow` and `apache-airflow-providers-slack` as dependencies

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard Airflow patterns for CeleryExecutor docker-compose setups.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
