---
phase: 03-warehouse-dbt
plan: 06
subsystem: infra
tags: [airflow, dbt, snowflake, dbt-core, dbt-snowflake, snowflake-connector-python, docker]

# Dependency graph
requires:
  - phase: 03-warehouse-dbt/03-02
    provides: dbt project scaffold (dbt_project.yml, models/, profiles.yml template)

provides:
  - cs2_dbt_run Airflow DAG with copy_into_raw >> dbt_run >> dbt_test pipeline
  - Updated Dockerfile with dbt-core, dbt-snowflake, snowflake-connector-python, cryptography
  - DAG structural tests (6 tests)

affects:
  - 04-analytics (will trigger dbt run to refresh warehouse for dashboard queries)
  - 06-ci (Dockerfile change affects Docker build time and image size)

# Tech tracking
tech-stack:
  added:
    - dbt-core==1.11.7 (added to Airflow Dockerfile)
    - dbt-snowflake==1.11.3 (added to Airflow Dockerfile)
    - snowflake-connector-python>=3.0 (added to Airflow Dockerfile)
    - cryptography>=41.0 (added to Airflow Dockerfile)
  patterns:
    - BashOperator for dbt CLI invocation (simpler than Cosmos, matches existing DAG patterns)
    - RSA key-pair auth for Snowflake (password auth dead Nov 2025)
    - dbt_project/ COPY into Docker image for BashOperator access
    - --profiles-dir flag on all dbt commands (avoids ~/.dbt/ not found in container)
    - @task() decorator for copy_into_raw (lazy snowflake.connector import inside task body)

key-files:
  created:
    - airflow/dags/cs2_dbt_run.py
    - tests/test_dags/test_dbt_run_dag.py
  modified:
    - airflow/Dockerfile

key-decisions:
  - "BashOperator chosen over Cosmos for dbt tasks — simpler, matches existing DAG patterns, no per-model observability needed yet"
  - "snowflake.connector imported inside @task() body — prevents module-level import error when package absent at DagBag load time"
  - "dbt_project/ COPYed at root USER level before airflow user pip install — chown=airflow:0 ensures correct file ownership"
  - "PURGE = FALSE on all COPY INTO statements — raw S3 layer remains intact as immutable source of truth"

patterns-established:
  - "Pattern: dbt CLI via BashOperator with --profiles-dir — use in all future dbt-calling DAGs"
  - "Pattern: Snowflake connector import inside @task() body — avoids DagBag load-time import errors"

requirements-completed: [WH-11, WH-12]

# Metrics
duration: 2min
completed: 2026-03-17
---

# Phase 3 Plan 6: cs2_dbt_run DAG + Dockerfile dbt Dependencies Summary

**Daily warehouse refresh DAG (COPY INTO raw S3 tables >> dbt run >> dbt test) with dbt-core 1.11.7 and key-pair Snowflake auth baked into Airflow Docker image**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-17T21:13:41Z
- **Completed:** 2026-03-17T21:15:25Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- cs2_dbt_run DAG orchestrates the full ELT refresh: COPY INTO 6 raw Snowflake tables from S3 stage, then dbt run through all model layers, then dbt test for data quality validation
- Dockerfile updated with dbt-core + dbt-snowflake + snowflake-connector-python + cryptography and dbt_project/ COPY to make dbt CLI available to BashOperator inside containers
- 6 DAG structural tests verify the 3-task pipeline, schedule, tags, and dependency chain; all 18 DAG tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Update Dockerfile + create cs2_dbt_run DAG** - `6a99237` (feat)
2. **Task 2: Create DAG structural test for cs2_dbt_run** - `a4788ab` (test)

## Files Created/Modified

- `airflow/dags/cs2_dbt_run.py` - cs2_dbt_run DAG with copy_into_raw (TaskFlow) >> dbt_run (BashOperator) >> dbt_test (BashOperator)
- `airflow/Dockerfile` - Added COPY dbt_project + dbt-core==1.11.7, dbt-snowflake==1.11.3, snowflake-connector-python>=3.0, cryptography>=41.0 to pip install
- `tests/test_dags/test_dbt_run_dag.py` - 6 structural tests: dag_loads, three_tasks, task_ids, schedule, tags, dependencies

## Decisions Made

- BashOperator was used for dbt_run and dbt_test tasks (not Cosmos) — simpler approach that matches existing DAG patterns; Cosmos adds per-model observability but is heavy and unnecessary at this stage
- snowflake.connector is imported inside the @task() function body (not at module level) — avoids DagBag load-time ImportError when snowflake-connector-python is absent in local dev environment, following the established Pitfall 3 pattern from RESEARCH.md
- PURGE = FALSE on all COPY INTO statements — never delete from S3 raw layer; it is the immutable source of truth for replay

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - DAG loaded on first run, all 6 structural tests passed immediately.

## User Setup Required

None - no external service configuration required for this plan. Snowflake credentials (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE) must be set in docker-compose environment when running the DAG in production.

## Next Phase Readiness

- cs2_dbt_run DAG is ready to orchestrate warehouse refreshes once Snowflake credentials are provisioned and dbt models are deployed
- The DAG depends on dbt_project/ having a valid profiles.yml (created in plan 03-02) and populated dbt models
- Phase 4 analytics products can trigger dbt refresh via this DAG or query mart tables directly after the DAG runs

---
*Phase: 03-warehouse-dbt*
*Completed: 2026-03-17*
