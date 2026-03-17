# Phase 2: Orchestration - Research

**Researched:** 2026-03-16
**Domain:** Apache Airflow 2.9, CeleryExecutor, Docker Compose, Slack Webhooks, DAG Testing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use `apache/airflow:2.9-python3.12` official image — matches Python 3.12 constraint
- CeleryExecutor + Redis broker — more prod-realistic stack, Redis broker explicitly required by ORC-05
- API secrets via `env_file: .env` — reuses existing `CS2_*` env var pattern, no extra secrets infra
- Healthchecks on webserver `:8080/health` — prevent startup race conditions
- TaskFlow API (`@task` decorator) — modern Python-native style, cleaner than classic PythonOperator
- Call async Phase 1 clients via `asyncio.run()` wrapper — direct reuse, no duplication
- S3 key existence check before ingesting — skip if today's Parquet already exists (stateless idempotency)
- Read config from `CS2_*` env vars at task runtime — consistent with established pattern, no Airflow Connections/Variables overhead
- Slack webhook for failure notifications — no SMTP config needed
- DAG-level `on_failure_callback` — catches any task failure without per-task boilerplate
- Alert content includes: DAG name, task ID, run_id, log URL
- `fail_intentionally` dev DAG to verify Slack webhook is live
- `pytest` + `dag.test()` for DAG structural and task-level tests
- Full type hints throughout DAG files
- `structlog` for logging in DAG tasks
- Manual first-run trigger via `airflow dags trigger` (documented in README)

### Claude's Discretion
- DAG file organization within `airflow/dags/` (one file per DAG vs shared utils module)
- Exact Postgres and Redis versions in docker-compose.yml
- Airflow webserver port mapping (default 8080)
- Volume mount strategy for DAGs directory

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ORC-01 | Airflow DAG `cs2_daily_matches` runs every 6h and ingests new match results | TaskFlow @task + asyncio.run() + S3 idempotency check pattern |
| ORC-02 | Airflow DAG `cs2_weekly_rankings` runs weekly and ingests team rankings | Same TaskFlow pattern with `schedule="@weekly"` |
| ORC-03 | Airflow DAG `cs2_tournament_sync` syncs active tournament data | Same TaskFlow pattern with appropriate schedule |
| ORC-04 | All DAGs have failure alerting (email or Slack webhook) | `on_failure_callback` with `SlackWebhookHook` at DAG level; provider 8.7.1 bundled with 2.9.3 constraints |
| ORC-05 | Docker Compose runs Airflow + Postgres metadata DB + Redis broker with one command | Official Airflow 2.9 docker-compose.yaml extended with custom Dockerfile for local package install |
</phase_requirements>

---

## Summary

Phase 2 wires the Phase 1 ingestion clients into a scheduled, monitored Airflow pipeline using a full CeleryExecutor stack running locally via Docker Compose. The official `apache/airflow:2.9-python3.12` image is extended with a custom Dockerfile to install the local `cs2_analytics` package, then a `docker-compose.yml` brings up Postgres (metadata DB), Redis (Celery broker), scheduler, webserver, worker, and triggerer services. Three DAGs use the TaskFlow API (`@task` decorator) to call async Phase 1 clients via `asyncio.run()` wrappers and apply S3 key existence checks for idempotency.

Slack failure alerting is implemented via `SlackWebhookHook` from `apache-airflow-providers-slack==8.7.1` (the version pinned in the Airflow 2.9.3 constraints file for Python 3.12). The webhook URL is consumed as a `CS2_SLACK_WEBHOOK_URL` env var to avoid adding Airflow Connections overhead. Testing covers structural DAG validation with `DagBag` and task-level logic via `dag.test()`, plus unit tests of the idempotency helpers with mocked boto3.

**Primary recommendation:** Extend the official Airflow 2.9 image with a Dockerfile that pip-installs the local package; keep one file per DAG plus a shared `airflow/dags/utils/slack_alerts.py` for the callback; use `CS2_*` env vars for all config, injected via `env_file: .env`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| apache-airflow | 2.9.x (image: apache/airflow:2.9-python3.12) | Pipeline orchestration — scheduler, webserver, CeleryExecutor | Locked decision; official image |
| apache-airflow-providers-slack | 8.7.1 | Slack webhook failure alerts | Pinned in constraints-2.9.3/constraints-3.12.txt |
| apache-airflow-providers-amazon | pinned by constraints | S3KeySensor (optional) + AWS integration | Required for any S3 sensor use |
| celery | pinned by constraints | Task queue for CeleryExecutor | Bundled with Airflow CeleryExecutor extras |
| redis | image: redis:7-alpine | Message broker for Celery | Lightweight, official; version at Claude's discretion |
| postgres | image: postgres:16 | Airflow metadata database | Stable LTS, official; version at Claude's discretion |
| structlog | >=24.0 | Structured logging in DAG tasks | Already in project dependencies |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pendulum | bundled with Airflow | Timezone-aware datetime for `start_date` | All DAG definitions — Airflow requires it for `@dag(start_date=...)` |
| boto3 | >=1.35 | S3 head_object for idempotency check | Inside `check_s3_key_exists()` helper |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom `on_failure_callback` with `SlackWebhookHook` | `send_slack_webhook_notification` (newer notifier API) | Notifier API requires Airflow Connections; direct webhook URL via env var avoids that overhead per locked decision |
| Single docker-compose with `_PIP_ADDITIONAL_REQUIREMENTS` | Custom Dockerfile + `build:` | `_PIP_ADDITIONAL_REQUIREMENTS` is slow (re-pip on every container start); Dockerfile bakes dependencies into image layer |

**Installation (added to pyproject.toml dependencies):**
```bash
# In Dockerfile (Airflow worker/scheduler/webserver):
pip install apache-airflow-providers-slack==8.7.1

# To run full stack locally:
docker compose up airflow-init
docker compose up
```

---

## Architecture Patterns

### Recommended Project Structure

```
airflow/
├── Dockerfile               # Extends apache/airflow:2.9-python3.12; pip installs local package
├── docker-compose.yml       # Postgres + Redis + scheduler + webserver + worker + triggerer
├── dags/
│   ├── cs2_daily_matches.py     # ORC-01: every 6h, FACEIT + PandaScore match ingestion
│   ├── cs2_weekly_rankings.py   # ORC-02: weekly, team rankings
│   ├── cs2_tournament_sync.py   # ORC-03: tournament metadata sync
│   ├── fail_intentionally.py    # Dev DAG — smoke test Slack webhook
│   └── utils/
│       └── slack_alerts.py      # shared on_failure_callback function
tests/
└── test_dags/
    ├── test_dag_structure.py    # DagBag import + task_ids structural tests
    ├── test_daily_matches.py    # Task logic unit tests with mocked clients
    ├── test_idempotency.py      # S3 key existence check logic
    └── conftest.py              # Airflow DAG test fixtures (reuses existing env dummy pattern)
```

### Pattern 1: TaskFlow DAG with asyncio.run() wrapper

**What:** Each DAG task is a `@task`-decorated function that wraps the async Phase 1 client in `asyncio.run()` to run synchronously inside Airflow's task process.

**When to use:** Every DAG task that calls a Phase 1 async ingestion client.

**Example:**
```python
# Source: Airflow TaskFlow docs + project async client pattern
from __future__ import annotations

import asyncio
from datetime import datetime

import pendulum
import structlog
from airflow.decorators import dag, task

from cs2_analytics.ingestion.faceit import FACEITClient
from cs2_analytics.utils.config import Settings
from airflow_dags.utils.slack_alerts import on_failure_callback

log = structlog.get_logger()

@dag(
    dag_id="cs2_daily_matches",
    schedule="0 */6 * * *",  # every 6 hours
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    on_failure_callback=on_failure_callback,
    tags=["cs2", "ingestion"],
)
def cs2_daily_matches_dag() -> None:

    @task()
    def check_and_ingest_matches() -> int:
        settings = Settings()
        # Idempotency: skip if today's Parquet already exists in S3
        today = datetime.utcnow().strftime("%Y-%m-%d")
        s3_key = f"raw/matches/faceit/{today}/matches.parquet"
        if _s3_key_exists(settings.aws_s3_bucket, s3_key):
            log.info("s3_key_already_exists", key=s3_key)
            return 0
        count = asyncio.run(_ingest_matches(settings))
        log.info("ingestion_complete", count=count)
        return count

    check_and_ingest_matches()

cs2_daily_matches_dag()
```

### Pattern 2: S3 Key Existence Idempotency Check

**What:** Before running ingestion, call `s3_client.head_object()`. If the object exists (no `ClientError`), skip the task by returning early. This ensures the task is safe to retry and backfill without duplicate data.

**When to use:** Opening step of every ingestion task in all three DAGs.

**Example:**
```python
# Source: boto3 docs + project s3.py pattern
import boto3
from botocore.exceptions import ClientError

def _s3_key_exists(bucket: str, key: str) -> bool:
    """Return True if key exists in S3 bucket, False otherwise."""
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            return False
        raise
```

### Pattern 3: DAG-Level Slack Failure Callback

**What:** A shared callback function registered at `on_failure_callback` on the DAG object. When any task in the DAG fails, Airflow calls this with the execution context.

**When to use:** All production DAGs. Not needed for `fail_intentionally` dev DAG (it intentionally fails).

**Example:**
```python
# Source: Airflow callbacks docs + gist.github.com/ddelange
from __future__ import annotations
import os
from typing import Any
import structlog
from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook

log = structlog.get_logger()

def on_failure_callback(context: dict[str, Any]) -> None:
    """Send Slack alert when any task in the DAG fails."""
    ti = context["ti"]
    dag_id: str = ti.dag_id
    task_id: str = ti.task_id
    run_id: str = context["run_id"]
    log_url: str = ti.log_url
    exception = context.get("exception", "No exception captured")

    message = (
        f":red_circle: *DAG Failure*\n"
        f"`DAG`   {dag_id}\n"
        f"`Task`  {task_id}\n"
        f"`Run`   {run_id}\n"
        f"`Error` {exception}\n"
        f"<{log_url}|View Logs>"
    )

    webhook_url = os.environ["CS2_SLACK_WEBHOOK_URL"]
    hook = SlackWebhookHook(webhook_url=webhook_url)
    hook.send(text=message)
    log.info("slack_failure_alert_sent", dag_id=dag_id, task_id=task_id)
```

### Pattern 4: Docker Compose Service Dependency Chain

**What:** Postgres and Redis must be healthy before Airflow services start. Use `healthcheck` + `depends_on: condition: service_healthy` in docker-compose.yml.

**When to use:** The docker-compose.yml for every service that depends on Postgres or Redis.

**Example:**
```yaml
# Source: official apache/airflow 2.9 docker-compose.yaml pattern
x-airflow-common: &airflow-common
  image: cs2-airflow:2.9-python3.12   # built from local Dockerfile
  env_file:
    - .env
  environment:
    AIRFLOW__CORE__EXECUTOR: CeleryExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__BROKER_URL: redis://:@redis:6379/0
    AIRFLOW__CORE__DAGS_FOLDER: /opt/airflow/dags
    AIRFLOW__CORE__FERNET_KEY: ""
    AIRFLOW__CORE__LOAD_EXAMPLES: "false"
    PYTHONPATH: /opt/airflow
  volumes:
    - ./airflow/dags:/opt/airflow/dags
    - ./logs:/opt/airflow/logs
    - ./src:/opt/airflow/src   # mounts project src into PYTHONPATH
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

### Pattern 5: Custom Dockerfile for Local Package

**What:** Extend the official Airflow image to install the local `cs2_analytics` package and the Slack provider. Avoids `_PIP_ADDITIONAL_REQUIREMENTS` which re-downloads on every container start.

```dockerfile
FROM apache/airflow:2.9-python3.12

USER root
COPY pyproject.toml /opt/cs2-analytics/pyproject.toml
COPY src /opt/cs2-analytics/src
RUN pip install --no-cache-dir /opt/cs2-analytics \
    apache-airflow-providers-slack==8.7.1

USER airflow
ENV PYTHONPATH="/opt/cs2-analytics/src:${PYTHONPATH}"
```

### Anti-Patterns to Avoid

- **`_PIP_ADDITIONAL_REQUIREMENTS` in production:** Reinstalls packages on every container start, causes slow startup and potential network failures. Use a custom Dockerfile instead.
- **`catchup=True`:** Default is `True` in Airflow — always set `catchup=False` unless backfilling is explicitly required. With 6h schedule and no catchup, a fresh install won't trigger hundreds of historical runs.
- **`start_date=datetime.now()`:** Dynamic `start_date` causes Airflow to miscalculate scheduling. Always use a fixed date like `pendulum.datetime(2024, 1, 1, tz="UTC")`.
- **Importing Settings at module level in DAG files:** Airflow imports all DAG files at scheduler startup. If Settings() raises (missing env var), all DAGs fail to load. Import Settings() inside task function bodies.
- **Per-task `on_failure_callback`:** Verbose and error-prone. Register once at DAG level; it applies to all tasks.
- **Using Airflow Connections for API keys:** The locked decision is `CS2_*` env vars — do not add `conn_id` parameters to the Slack hook or any other hook. Read from `os.environ` directly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Slack message delivery | Custom HTTP POST to Slack API | `SlackWebhookHook` from `apache-airflow-providers-slack` | Handles retries, auth headers, message formatting, and Airflow context |
| Task retry with backoff | Custom retry loop in task | `retries` + `retry_delay` + `retry_exponential_backoff` on `@dag(default_args=...)` | Airflow handles retry state in metadata DB, visible in UI |
| Container health gating | Custom startup scripts | Docker Compose `healthcheck` + `depends_on: condition: service_healthy` | Native compose feature, no shell scripting needed |
| DAG dependency resolution | Manual task ordering | TaskFlow automatic dependency inference from return values | XCom handles inter-task data passing automatically |
| Idempotency via database | Separate tracking table | S3 `head_object` check on output key | Stateless — uses the artifact that would be produced as the state signal |

**Key insight:** Airflow already solves retry, state tracking, and dependency resolution. The only custom code needed is the business logic (calling ingestion clients and checking S3 keys).

---

## Common Pitfalls

### Pitfall 1: catchup=True Backfill Flood

**What goes wrong:** On first `docker compose up`, Airflow sees a DAG with `start_date=2024-01-01` and `schedule="0 */6 * * *"` — it immediately queues thousands of missed runs.
**Why it happens:** `catchup` defaults to `True` in Airflow 2.x.
**How to avoid:** Always set `catchup=False` explicitly in the `@dag` decorator. Also document in README: use `airflow dags trigger cs2_daily_matches` for the first run.
**Warning signs:** Airflow UI shows hundreds of queued/running DAG runs immediately after startup.

### Pitfall 2: Dynamic start_date

**What goes wrong:** Using `start_date=datetime.now()` or `start_date=datetime.utcnow()` causes DAG scheduling to be unpredictable — Airflow evaluates this at import time, and a re-import gives a different start_date.
**Why it happens:** DAG files are re-imported by the scheduler periodically.
**How to avoid:** Use a fixed `pendulum.datetime(2024, 1, 1, tz="UTC")`.
**Warning signs:** DAG runs appear at unexpected times or fail to schedule.

### Pitfall 3: Module-Level Settings() Import in DAG Files

**What goes wrong:** `from cs2_analytics.utils.config import settings` at the top of a DAG file fails if `CS2_*` env vars are missing from the scheduler container. This causes ALL DAGs to fail to load (shown as import errors in DagBag).
**Why it happens:** Airflow imports DAG files to discover tasks. Any import error marks the DAG as broken.
**How to avoid:** Import `Settings()` inside the `@task` function body, not at module level.
**Warning signs:** DagBag reports import errors; DAGs disappear from Airflow UI.

### Pitfall 4: PYTHONPATH Not Set in All Containers

**What goes wrong:** `from cs2_analytics.ingestion.faceit import FACEITClient` raises `ModuleNotFoundError` in the worker container even though it works in the scheduler.
**Why it happens:** Scheduler and worker are separate containers; PYTHONPATH must be set identically in both (via the `x-airflow-common` anchor in docker-compose.yml).
**How to avoid:** Set `PYTHONPATH: /opt/cs2-analytics/src` in the `x-airflow-common` environment block so it inherits to all services.
**Warning signs:** Tasks fail with `ModuleNotFoundError` but DAG loads fine in scheduler logs.

### Pitfall 5: asyncio.run() Inside Already-Running Event Loop

**What goes wrong:** If Airflow is run with a `SequentialExecutor` or in a testing context that already has an event loop, `asyncio.run()` raises `RuntimeError: This event loop is already running`.
**Why it happens:** `asyncio.run()` creates a new event loop but fails if one already exists in the thread.
**How to avoid:** In unit tests, call the async function directly with `await` or use `pytest-asyncio`. In production with CeleryExecutor, each worker task runs in a fresh process — `asyncio.run()` is safe.
**Warning signs:** `RuntimeError: This event loop is already running` in task logs during testing.

### Pitfall 6: Slack Provider Version Incompatibility

**What goes wrong:** Installing `apache-airflow-providers-slack` latest (9.x) alongside Airflow 2.9 raises dependency conflicts — the latest provider requires Airflow >= 2.11.
**Why it happens:** Provider packages are released independently and version constraints are strict.
**How to avoid:** Pin to `apache-airflow-providers-slack==8.7.1` — the version in the Airflow 2.9.3 + Python 3.12 constraints file.
**Warning signs:** `pip` dependency solver errors during Dockerfile build.

### Pitfall 7: Missing AIRFLOW_UID on Linux

**What goes wrong:** Files written to mounted volumes (./dags, ./logs) are owned by root inside the container, causing permission errors when Airflow tries to write scheduler logs or when DAG files are updated from the host.
**Why it happens:** Linux Docker runs containers as the image's user (UID 50000 by default for Airflow), but the host directory may have different ownership.
**How to avoid:** Add `AIRFLOW_UID=$(id -u)` to `.env` before running `docker compose up airflow-init`. Document this in README.
**Warning signs:** `PermissionError` in scheduler or task logs; logs volume shows root-owned files.

---

## Code Examples

Verified patterns from official sources and constraints:

### DAG Skeleton (TaskFlow API)

```python
# Source: https://airflow.apache.org/docs/apache-airflow/2.9.1/tutorial/taskflow.html
from __future__ import annotations

import pendulum
from airflow.decorators import dag, task

@dag(
    dag_id="cs2_daily_matches",
    schedule="0 */6 * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    tags=["cs2", "ingestion"],
    on_failure_callback=on_failure_callback,
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(minutes=5),
        "retry_exponential_backoff": True,
    },
)
def cs2_daily_matches_dag() -> None:

    @task()
    def ingest_faceit_matches() -> int:
        # Settings() called here, not at module level
        ...

    @task()
    def ingest_pandascore_matches() -> int:
        ...

    # TaskFlow infers dependency from function call order
    faceit_count = ingest_faceit_matches()
    pandascore_count = ingest_pandascore_matches()

cs2_daily_matches_dag()
```

### DagBag Structural Test

```python
# Source: Airflow best practices + Astronomer testing guide
import pytest
from airflow.models import DagBag

@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder="airflow/dags", include_examples=False)

def test_no_import_errors(dagbag: DagBag) -> None:
    assert not dagbag.import_errors, f"DAG import errors: {dagbag.import_errors}"

def test_daily_matches_dag_exists(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("cs2_daily_matches")
    assert dag is not None

def test_daily_matches_task_ids(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("cs2_daily_matches")
    assert dag is not None
    expected = {"ingest_faceit_matches", "ingest_pandascore_matches"}
    assert expected.issubset(set(dag.task_ids))

def test_daily_matches_schedule(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("cs2_daily_matches")
    assert dag is not None
    assert str(dag.schedule_interval) == "0 */6 * * *"
```

### Callback Context Variables

```python
# Source: Airflow callbacks docs 2.9.3 + gist.github.com/ddelange
from typing import Any

def on_failure_callback(context: dict[str, Any]) -> None:
    ti = context["ti"]
    dag_id: str = ti.dag_id
    task_id: str = ti.task_id
    run_id: str = context["run_id"]
    log_url: str = ti.log_url
    exception: str = str(context.get("exception", "unknown"))
    # ... format and send Slack message
```

### docker-compose.yml Init Sequence

```bash
# Source: official Airflow 2.9 Docker docs
# Step 1: create dirs and set UID
mkdir -p ./airflow/dags ./logs ./plugins
echo "AIRFLOW_UID=$(id -u)" >> .env

# Step 2: build custom image
docker compose build

# Step 3: initialize metadata DB and create admin user
docker compose up airflow-init

# Step 4: start all services
docker compose up -d

# Step 5: trigger first run manually (avoid backfill confusion)
docker compose exec airflow-webserver airflow dags trigger cs2_daily_matches
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `PythonOperator(python_callable=fn)` | `@task` decorator (TaskFlow API) | Airflow 2.0 (2020) | Cleaner code, automatic XCom, no manual operator instantiation |
| `SlackWebhookOperator` | `SlackWebhookHook.send()` inside callback | Provider 8.x | Operator requires task_id; hook is usable in any callback context |
| `send_slack_webhook_notification` (notifier) | `SlackWebhookHook` with env var URL | Provider 8.3+ | Notifier requires Airflow Connection object; hook allows direct URL injection |
| Separate `airflow-init` container | `airflow db migrate` + `airflow users create` | Airflow 2.7+ | Functionally equivalent; official compose uses init container pattern |
| `DAG(schedule_interval=...)` | `DAG(schedule=...)` | Airflow 2.4 | `schedule_interval` deprecated; use `schedule` |

**Deprecated/outdated:**
- `PythonOperator` for new DAGs: still works but TaskFlow is preferred for type safety and XCom ergonomics
- `schedule_interval` parameter: replaced by `schedule` in Airflow 2.4+
- `SlackWebhookOperator` for callbacks: requires `task_id` which is awkward outside of task context

---

## Open Questions

1. **Slack webhook URL delivery**
   - What we know: `CS2_SLACK_WEBHOOK_URL` env var will be in `.env`, injected via `env_file: .env`
   - What's unclear: Which Slack workspace/channel to use during development (personal workspace)
   - Recommendation: Document "create a Slack app with Incoming Webhooks" in README; use a dev channel for testing; `fail_intentionally` DAG proves the path works

2. **Airflow Fernet key generation**
   - What we know: `AIRFLOW__CORE__FERNET_KEY` is required for encrypting Connection passwords in the metadata DB; can be empty string if no Connections are used (we are not using Connections)
   - What's unclear: Whether empty string causes Airflow startup warnings or errors
   - Recommendation: Generate once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, store in `.env` as `CS2_AIRFLOW_FERNET_KEY`

3. **Test isolation for DagBag tests**
   - What we know: DagBag loads actual DAG files and imports them, so `CS2_*` env vars must be set before `DagBag()` is instantiated
   - What's unclear: Whether the existing `tests/conftest.py` dummy env var pattern will cover DAG tests automatically or if a separate `tests/test_dags/conftest.py` is needed
   - Recommendation: Create `tests/test_dags/conftest.py` that imports `_DUMMY_ENV` from the parent conftest and adds `CS2_SLACK_WEBHOOK_URL=test_webhook_url`

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_dags/ -x -q` |
| Full suite command | `uv run pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORC-01 | `cs2_daily_matches` DAG loads without errors | unit (structural) | `uv run pytest tests/test_dags/test_dag_structure.py -x` | Wave 0 |
| ORC-01 | `cs2_daily_matches` tasks ingest and skip when S3 key exists | unit (logic) | `uv run pytest tests/test_dags/test_daily_matches.py -x` | Wave 0 |
| ORC-01 | Schedule is `"0 */6 * * *"` | unit (structural) | `uv run pytest tests/test_dags/test_dag_structure.py::test_daily_matches_schedule -x` | Wave 0 |
| ORC-02 | `cs2_weekly_rankings` DAG loads without errors | unit (structural) | `uv run pytest tests/test_dags/test_dag_structure.py -x` | Wave 0 |
| ORC-03 | `cs2_tournament_sync` DAG loads without errors | unit (structural) | `uv run pytest tests/test_dags/test_dag_structure.py -x` | Wave 0 |
| ORC-04 | `on_failure_callback` sends Slack message with correct fields | unit (logic) | `uv run pytest tests/test_dags/test_slack_alerts.py -x` | Wave 0 |
| ORC-05 | `docker compose up` success / smoke test | manual (smoke) | `docker compose up -d && docker compose ps` | manual-only |

**Manual-only justification for ORC-05:** Starting a full Docker Compose stack with Postgres + Redis + Airflow scheduler in a pytest context is impractical in < 30 seconds and requires Docker daemon. Smoke tested manually after implementation.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_dags/ -x -q`
- **Per wave merge:** `uv run pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_dags/__init__.py` — makes test_dags a package
- [ ] `tests/test_dags/conftest.py` — extends root conftest with `CS2_SLACK_WEBHOOK_URL` dummy and DagBag fixture
- [ ] `tests/test_dags/test_dag_structure.py` — covers ORC-01, ORC-02, ORC-03 structural requirements
- [ ] `tests/test_dags/test_daily_matches.py` — covers ORC-01 task logic with mocked FACEITClient + PandaScoreClient
- [ ] `tests/test_dags/test_slack_alerts.py` — covers ORC-04 callback with mocked SlackWebhookHook
- [ ] `airflow/dags/utils/__init__.py` — package init
- [ ] Framework install: `apache-airflow` and `apache-airflow-providers-slack==8.7.1` added to `pyproject.toml` dev deps

---

## Sources

### Primary (HIGH confidence)

- `https://airflow.apache.org/docs/apache-airflow/2.9.0/howto/docker-compose/index.html` — official docker-compose setup, service definitions, volume mounts
- `https://airflow.apache.org/docs/apache-airflow/2.9.1/tutorial/taskflow.html` — TaskFlow @task and @dag decorators, XCom, multiple_outputs
- `https://airflow.apache.org/docs/apache-airflow/2.9.3/administration-and-deployment/logging-monitoring/callbacks.html` — callback types, function signature, context variables
- `https://raw.githubusercontent.com/apache/airflow/constraints-2.9.3/constraints-3.12.txt` — `apache-airflow-providers-slack==8.7.1` verified pin for Airflow 2.9.3 + Python 3.12
- `https://airflow.apache.org/docs/apache-airflow-providers-slack/stable/notifications/slackwebhook_notifier_howto_guide.html` — official Slack webhook notification examples

### Secondary (MEDIUM confidence)

- `https://www.astronomer.io/docs/learn/testing-airflow` — DagBag structural test pattern, dag.test() usage (Astronomer = Airflow's primary commercial backer, high trust)
- `https://gist.github.com/ddelange/6e33f8f0df3a97d4a371d055aa2d58ac` — context variable extraction pattern for failure callback (`ti.dag_id`, `ti.task_id`, `context["run_id"]`, `ti.log_url`)

### Tertiary (LOW confidence)

- WebSearch summaries for general Docker Compose + PYTHONPATH patterns (verified against official docs before inclusion)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against official Airflow 2.9.3 constraints file for Python 3.12
- Architecture: HIGH — TaskFlow patterns from official docs; Docker Compose from official guide
- Pitfalls: HIGH for catchup/start_date/import-level (well-documented in official best practices); MEDIUM for PYTHONPATH (verified via multiple community sources, pattern consistent)
- Testing: HIGH for DagBag structural tests; MEDIUM for dag.test() integration (pattern verified against Astronomer docs)

**Research date:** 2026-03-16
**Valid until:** 2026-09-16 (Airflow 2.9.x is stable; providers versioning is stable at 8.7.1 pin)
