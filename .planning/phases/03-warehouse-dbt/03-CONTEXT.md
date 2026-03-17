# Phase 3: Warehouse & dbt - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers a Snowflake data warehouse with dbt Core models transforming raw S3 Parquet data into seven analytical marts. Covers: Snowflake schema setup, external stage pointing at S3 `raw/` prefix, COPY INTO loading, dbt staging/intermediate/mart models, schema tests, and lineage documentation. Also includes a small canonical Match model patch (adding score fields) to support choke/clutch metrics, and a new Airflow DAG (`cs2_dbt_run`) to orchestrate the warehouse refresh.

</domain>

<decisions>
## Implementation Decisions

### Snowflake Setup & External Stage
- Load raw S3 Parquet into Snowflake via external stage + COPY INTO — standard ELT pattern
- Database: CS2_ANALYTICS with three schemas: RAW, STAGING, MARTS — clear separation matching dbt layers
- Credentials: environment variables (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE) — consistent with existing CS2_* env var pattern
- New Airflow DAG `cs2_dbt_run` triggers COPY INTO staging then `dbt run && dbt test` daily after match ingestion

### dbt Project Structure & Materialization
- dbt project at `dbt_project/` in repo root — matches CLAUDE.md Phase 3 directory
- Staging models materialized as views — lightweight, always fresh, no storage cost
- Mart models materialized as tables — pre-computed for dashboard query speed, rebuilt each dbt run
- Tests: schema tests (not_null, unique, relationships) + custom singular tests for business logic — covers WH-11

### Staging & Intermediate Model Design
- Multi-source matches: `int_matches_unioned` intermediate model — UNION ALL from stg_faceit_matches, stg_pandascore_matches, stg_kaggle_matches with source column preserved
- Multi-source players: `int_players_unioned` — same UNION ALL pattern, deduplicate by player_id + source priority (FACEIT > PandaScore for stats)
- dim_maps: extracted from DISTINCT map_name in matches
- dim_tournaments: extracted from Liquipedia tournament metadata in S3
- Naming: `stg_{source}_{entity}` — e.g., stg_faceit_matches, stg_liquipedia_teams

### Mart Layer Design & Feature Engineering
- mart_upset_features: upset defined as lower-ranked team wins with world_ranking delta > 5
- mart_hidden_gems: tier boundaries — Tier 1: rank 1-10, Tier 2: 11-30, Tier 3: 31+ (per HG-01)
- mart_choke_profile: uses real score data after Match model patch — lead-blown = lost after leading 10+ rounds (CC-01), comeback = win when trailing 3+ at halftime (CC-02), overtime from score fields (CC-03), bracket position from Liquipedia metadata (CC-04)
- Match model patch: add score_a, score_b, is_overtime fields to canonical Match model + update all ingestion clients to populate them

### Claude's Discretion
- Intermediate model join logic and column pruning
- dbt macro usage for DRY patterns (e.g., source freshness, surrogate keys)
- Exact Snowflake warehouse size (X-SMALL default)
- profiles.yml env var naming beyond the decided pattern

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/cs2_analytics/models/canonical.py` — Match, Player, Team Pydantic models (Match needs score patch)
- `src/cs2_analytics/utils/s3.py` — S3 upload utilities, raw/ prefix with Hive partitioning
- `src/cs2_analytics/utils/config.py` — Settings with CS2_* env vars
- `airflow/dags/utils/slack_alerts.py` — Slack failure callback for new DAG

### Established Patterns
- Hive partitioning: `raw/{source}/{entity_type}/year={y}/month={m}/day={d}/`
- Pydantic v2 with ConfigDict, extra="forbid" for canonical models
- Environment variable config via pydantic-settings
- respx for mocking httpx in tests

### Integration Points
- External stage reads from S3 `raw/` prefix — path format must match existing ingestion output
- Airflow DAG `cs2_dbt_run` follows existing DAG patterns (slack_alerts, catchup=False)
- Phase 4 (Analytical Products) reads from mart tables — mart schemas must match ML feature expectations
- Phase 5 (Dashboard) queries marts via Snowflake connector — table materialization ensures query speed

</code_context>

<specifics>
## Specific Ideas

- Match model patch is a prerequisite for accurate choke/clutch metrics — should be planned as the first task in Phase 3
- Ingestion client updates (FACEIT, PandaScore, Kaggle) need to populate new score fields where available from API responses
- Snowflake setup SQL should be version-controlled in `dbt_project/setup/` for reproducibility

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
