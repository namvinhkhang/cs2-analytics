---
phase: 03-warehouse-dbt
plan: 02
subsystem: database
tags: [dbt, snowflake, sql, parquet, s3, warehouse]

# Dependency graph
requires:
  - phase: 02-orchestration
    provides: Airflow DAGs that will trigger dbt via cs2_dbt_run

provides:
  - dbt_project/ directory with full configuration scaffold
  - Snowflake DDL for CS2_ANALYTICS database, RAW/STAGING/MARTS schemas
  - External stage + COPY INTO patterns for S3 Parquet loading
  - TRANSFORMER role with least-privilege grants
  - dbt sources.yml declaring all 6 raw source tables

affects:
  - 03-03 (staging models reference sources.yml source declarations)
  - 03-04 (intermediate models depend on staging model structure)
  - 03-05 (mart models depend on intermediate layer)
  - 03-06 (cs2_dbt_run DAG depends on dbt_project/ scaffold)

# Tech tracking
tech-stack:
  added:
    - dbt-core 1.11.7
    - dbt-snowflake 1.11.3
    - dbt-labs/dbt_utils 1.3.0
    - snowflake-connector-python (Airflow DAG dependency, Plan 06)
    - cryptography (RSA key-pair auth, Plan 06)
  patterns:
    - dbt profile using env_var() for all Snowflake credentials (no hardcoded values)
    - RSA key-pair auth via SNOWFLAKE_PRIVATE_KEY env var (password auth dead Nov 2025)
    - Typed raw table schema + MATCH_BY_COLUMN_NAME for clean Parquet COPY INTO
    - Idempotent DDL throughout setup SQL (IF NOT EXISTS / CREATE OR REPLACE)

key-files:
  created:
    - dbt_project/dbt_project.yml
    - dbt_project/packages.yml
    - dbt_project/profiles.yml
    - dbt_project/.gitignore
    - dbt_project/setup/snowflake_setup.sql
    - dbt_project/models/sources.yml
    - dbt_project/models/staging/.gitkeep
    - dbt_project/models/intermediate/.gitkeep
    - dbt_project/models/marts/core/.gitkeep
    - dbt_project/models/marts/analytics/.gitkeep
    - dbt_project/macros/.gitkeep
    - dbt_project/tests/.gitkeep
  modified:
    - .gitignore
    - .env.example

key-decisions:
  - "Typed raw table schema + MATCH_BY_COLUMN_NAME over VARIANT column — avoids $1:field::type syntax in staging models and makes column lineage visible in dbt docs"
  - "profiles.yml not committed to git — .gitignore in both dbt_project/ and repo root exclude it; template kept on disk for developer setup"
  - "AUTO_SUSPEND = 60 and INITIALLY_SUSPENDED = TRUE on CS2_WH — prevents Snowflake free trial credit burn from idle warehouse"
  - "PURGE = FALSE in all COPY INTO commands — raw S3 data is never deleted after loading, preserving raw layer integrity"

patterns-established:
  - "Pattern: profiles.yml uses {{ env_var('SNOWFLAKE_*') }} exclusively — all creds from environment, never hardcoded"
  - "Pattern: staging layer reads from {{ source('raw', 'raw_<entity>') }} declared in sources.yml"
  - "Pattern: dbt_project.yml sets +schema per layer (STAGING for stg/int, MARTS for mart models)"

requirements-completed: [WH-01, WH-12]

# Metrics
duration: 2min
completed: 2026-03-17
---

# Phase 3 Plan 02: dbt Project Scaffold Summary

**dbt project scaffolded with Snowflake key-pair auth, typed raw table DDL for 6 sources, and sources.yml declarations — complete foundation for all subsequent staging and mart model plans**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-17T21:04:34Z
- **Completed:** 2026-03-17T21:07:24Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- `dbt_project/dbt_project.yml` configures staging/intermediate as views in STAGING schema and marts as tables in MARTS schema
- `dbt_project/setup/snowflake_setup.sql` creates all 8 Snowflake objects idempotently: database, 3 schemas, warehouse (X-SMALL with AUTO_SUSPEND), storage integration, external stage, 6 typed raw tables, and TRANSFORMER role with least-privilege grants
- `dbt_project/models/sources.yml` declares all 6 RAW schema tables so staging models reference them via `{{ source('raw', '...') }}`
- `profiles.yml` uses RSA key-pair auth via `SNOWFLAKE_PRIVATE_KEY` env var — required since Snowflake eliminated password auth for service accounts November 2025

## Task Commits

Each task was committed atomically:

1. **Task 1: Create dbt project config files** - `cda1457` (feat)
2. **Task 2: Create Snowflake setup SQL and dbt sources.yml** - `b69462b` (feat)

## Files Created/Modified
- `dbt_project/dbt_project.yml` - dbt project config: name, profile, paths, per-layer materializations
- `dbt_project/packages.yml` - dbt-labs/dbt_utils 1.3.0 dependency
- `dbt_project/profiles.yml` - Snowflake connection via RSA key-pair auth (not committed)
- `dbt_project/.gitignore` - excludes profiles.yml, target/, dbt_packages/, logs/
- `dbt_project/setup/snowflake_setup.sql` - idempotent DDL: database, schemas, warehouse, storage integration, stage, 6 raw tables, TRANSFORMER role + grants
- `dbt_project/models/sources.yml` - RAW schema declarations for all 6 source tables
- `.gitignore` - added dbt_project/ build output exclusions
- `.env.example` - added SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE

## Decisions Made
- **Typed raw tables over VARIANT**: Used `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` in COPY INTO with typed column definitions. This avoids `$1:field::type` Snowflake VARIANT syntax in staging models and makes column-level lineage visible in dbt docs.
- **profiles.yml not committed**: The file exists on disk as developer documentation but is excluded from git by both `dbt_project/.gitignore` and root `.gitignore`. Developers copy the template and set env vars.
- **AUTO_SUSPEND = 60**: Snowflake X-SMALL warehouse suspends after 60s idle. Combined with `INITIALLY_SUSPENDED = TRUE`, this prevents free trial credit burn during development.
- **PURGE = FALSE in COPY INTO**: Raw S3 Parquet files are never deleted after loading into Snowflake. Preserves raw data layer for re-loading and debugging.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `profiles.yml` was initially added to `git add` but was correctly rejected by `.gitignore` (expected behavior — the gitignore rule was working properly).

## User Setup Required

**External services require manual configuration before dbt can connect to Snowflake.**

Steps required before running `dbt run`:

1. **Create Snowflake account** (if not already done) — free trial at snowflake.com
2. **Run `dbt_project/setup/snowflake_setup.sql`** as ACCOUNTADMIN in a Snowflake worksheet
   - Replace `<your_iam_role_arn>` and `<your_bucket>` with actual values
3. **Get storage integration values**: Run `DESC INTEGRATION cs2_s3_int;` to retrieve `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID`
4. **Create AWS IAM role**: Add Snowflake's IAM user ARN and external ID to the trust policy
5. **Generate RSA key pair**:
   ```bash
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
   openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
   ```
6. **Register public key**: `ALTER USER <your_user> SET RSA_PUBLIC_KEY='<pub_key_without_headers>';`
7. **Set env vars** in `.env`:
   ```
   SNOWFLAKE_ACCOUNT=orgname-accountname
   SNOWFLAKE_USER=<your_user>
   SNOWFLAKE_PRIVATE_KEY=<full_pem_content_with_\n_newlines>
   SNOWFLAKE_WAREHOUSE=CS2_WH
   SNOWFLAKE_DATABASE=CS2_ANALYTICS
   ```
8. **Install dbt**: `pip install dbt-core==1.11.7 dbt-snowflake==1.11.3`
9. **Install dbt packages**: `cd dbt_project && dbt deps`
10. **Verify connection**: `dbt debug --profiles-dir /path/to/dbt_project`

## Next Phase Readiness
- dbt project scaffold complete — all subsequent plans (03-03 through 03-07) have a valid `dbt_project.yml` and `sources.yml` to build on
- Snowflake setup SQL is ready to run once Snowflake account is provisioned
- User must complete Snowflake + AWS IAM setup before any `dbt run` can succeed
- No Python code changes in this plan — existing 170 tests still pass

---
*Phase: 03-warehouse-dbt*
*Completed: 2026-03-17*
