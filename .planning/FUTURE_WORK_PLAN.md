# v1 Future Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the final v1 product gap by building a trustworthy Choke/Clutch team profile and adding its dashboard page. CS API bootstrap profiles, the Upset Tracker dashboard, the Hidden Gem Scout dashboard, browser checks, and scheduled dashboard refresh automation are already implemented.

**Architecture:** Keep Snowflake and dbt as the source of truth. Ingestion profiles write raw Parquet, dbt converts raw data into stable marts, and the dashboard reads cached mart snapshots plus versioned ML artifacts.

**Tech Stack:** Python, Pydantic, boto3, CS API, Snowflake, dbt, XGBoost, SHAP, Streamlit, Plotly, pytest.

---

## Current State

- Upset Tracker is trained from CS API-backed `mart_upset_features`.
- Hidden Gem Scout uses CS API player stats, current-team snapshots, team ranking tiers, tier-above thresholds, 90-day benchmark-gap trends, and a 20-row recent eligibility floor.
- CS API `daily`, `weekly`, and `backfill` profiles are implemented with bounded defaults, environment overrides, S3 skip-existing checks, Airflow wiring, and tests.
- The Streamlit dashboard ships Home, Upset Tracker, and Hidden Gem Scout pages backed by local mart snapshots and versioned ML artifacts.
- Dashboard browser smoke tests, desktop/mobile screenshot checks, and GitHub Actions dashboard refresh automation are implemented.
- Choke Profile has a best-effort `hltv_unofficial` round-history ingestion path, a sample-aware backend mart contract, cached snapshot export support, and a dashboard analysis page. Current local data is still growing, so Snowflake/dbt warehouse verification should continue with weekly HLTV batches.
- Player-level clutch, bracket, and elimination-match pressure remain out of v1 scope unless trustworthy event/bracket source data is added later.

## Workstream 1: Choke/Clutch Team Profile

**Goal:** Produce a team-level pressure profile that is honest about data quality, backed by enough maps to be meaningful, and visible in the dashboard as an analysis feature.

**Files:**
- Modify: `scripts/bootstrap_hltv_round_history.py`
- Modify: `src/cs2_analytics/ingestion/hltv.py`
- Modify: `src/cs2_analytics/models/hltv.py` if the cached payload shape expands.
- Modify: `src/cs2_analytics/utils/parquet.py` if new raw fields are added.
- Modify: `dashboard/export_snapshots.py`
- Create: `dashboard/pages/3_Choke_Clutch_Profile.py`
- Modify: `dbt_project/models/marts/analytics/mart_choke_profile.sql`
- Modify: `dbt_project/models/marts/analytics/analytics.yml`
- Modify: `dbt_project/models/staging/staging.yml`
- Test: `tests/test_hltv_round_history.py`
- Test: `tests/test_bootstrap_hltv_round_history.py`
- Test: `tests/test_marts/test_choke_profile_sql.py`
- Test: `tests/test_dashboard_export.py`
- Test: `tests/test_dashboard_pages.py`

- [x] Audit CS API, PandaScore, and FACEIT payloads for round score, halftime score, overtime, bracket stage, and elimination-match signals.
- [x] Document which pressure metrics can be exact and which must remain proxy-based.
  - 2026-05-11 decision: keep the v1 path CS API-first to preserve team ID alignment.
  - CS API `/matches/` map scores can support exact map W/L and inferred CS2 overtime when map total rounds are greater than 24.
  - Lead-blown, halftime comeback, bracket, and elimination metrics must stay proxy/unavailable until true round or bracket data is ingested with an identity map.
- [x] Add failing tests for unofficial HLTV round-history payload parsing.
- [x] Add typed raw model fields for HLTV round rows, including side winners, team winners, score state, map name, played date, and inferred CS2 overtime.
- [x] Add a cached JSON bootstrap path for HLTV mapstats.
- [x] Add raw Snowflake table, `COPY INTO`, dbt source, and staging model for HLTV round history.
- [x] Rebuild `mart_choke_profile` with:
  - exact map W/L record,
  - exact inferred overtime win/loss record,
  - exact largest-lead, 5+ lead-blown, halftime collapse, and halftime comeback metrics,
  - null bracket/elimination metrics until trustworthy source data exists,
  - metric quality flags for exact and unavailable metrics.

### Phase 1: Batch-Safe HLTV Raw Uploads

**Goal:** Let the feature ship against the current sample while supporting continued collection toward 5k valid maps without overwriting raw S3 files.

- [x] Add batch upload controls to `scripts/bootstrap_hltv_round_history.py`:
  - `--batch-id`, optional human-readable ID such as `pgl_astana_001` or `2026-05-12_001`.
  - `--filename`, still supported for explicit one-off names.
  - default filename should become unique when `--upload-s3` is used, for example `batch_<batch_id>.parquet` or `round_history_<YYYYMMDD_HHMMSS>.parquet`.
  - reject unsafe filenames with path separators.
- [x] Add an S3 skip-existing guard before upload so rerunning the same batch does not overwrite raw history.
- [x] Print and log batch summary:
  - total JSON files scanned,
  - valid map files parsed,
  - skipped/invalid JSON files,
  - total round rows written,
  - output S3 key or local Parquet path.
- [x] Keep invalid/null placeholder JSON files skipped, not fatal.
- [x] Add tests for:
  - unique batch filename generation,
  - `--batch-id` output naming,
  - skip-existing behavior,
  - invalid JSON files not blocking valid maps.
- [x] Recommended run pattern:
  - upload current sample as `--batch-id current_sample_001`,
  - continue fetching JSON in chunks,
  - upload later chunks as `--batch-id hltv_maps_002`, `hltv_maps_003`, etc.

### Phase 2: Mart Contract and Sample Quality

**Goal:** Make `mart_choke_profile` safe to display even when the dataset is small.

- [x] Add sample-size fields to `mart_choke_profile`:
  - `maps_analyzed`,
  - `rounds_analyzed`,
  - `overtime_maps_analyzed`,
  - `close_maps_analyzed`,
  - `maps_with_5plus_lead`,
  - `minimum_stable_maps`.
- [x] Add `sample_quality` with clear buckets:
  - `limited` for `< 20` maps,
  - `directional` for `20-49` maps,
  - `stable` for `>= 50` maps.
- [x] Add display-safe rates:
  - keep raw rates nullable when denominators are zero,
  - add dashboard-friendly coalesced fields only if needed,
  - avoid ranking teams by rates when denominator is too small.
- [x] Add league-average comparison fields:
  - `lead_blown_rate_delta`,
  - `halftime_comeback_rate_delta`,
  - `ot_win_rate_delta`,
  - `close_map_win_rate_delta`.
- [x] Add metric availability flags:
  - `round_history_available`,
  - `halftime_data_available`,
  - `clutch_data_available = false`,
  - `bracket_data_available = false`,
  - `sample_size_warning`.
- [x] Add dbt schema tests:
  - one row per `team_id`,
  - accepted values for `sample_quality`,
  - non-negative count fields,
  - accepted values for `metric_source`,
  - not-null required display fields.
- [x] Add SQL contract tests that prove:
  - `dim_teams` joins by HLTV `team_id`,
  - sample-quality buckets exist,
  - clutch/bracket flags remain false/null until real source data exists.

### Phase 3: Warehouse Verification With Current Data

**Goal:** Implement the feature against the current sample, then let confidence improve as more HLTV maps arrive.

- [ ] Upload current parsed sample to S3 with a batch ID. Local snapshot generation used the current cache; S3 upload still requires AWS credentials.
- [x] Run the GitHub Actions weekly profile or Airflow `cs2_dbt_run` to load `raw_hltv_round_history`.
- [x] Run targeted dbt locally or through CI:
  - `uv run dbt run --select +mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project`
  - `uv run dbt test --select +mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project`
- [x] Inspect `mart_choke_profile` for:
  - row count,
  - teams with `limited`, `directional`, and `stable` samples,
  - top/bottom pressure metrics,
  - null/zero denominator behavior.
- [x] Record current sample stats in `tasks/todo.md`:
  - JSON files fetched,
  - valid maps parsed,
  - skipped placeholders,
  - round rows loaded,
  - teams with at least 20 maps,
  - teams with at least 50 maps.

### Phase 4: Snapshot Export

**Goal:** Make the Choke Profile dashboard read cached snapshots like the existing pages.

- [x] Add `mart_choke_profile` to `dashboard/export_snapshots.py`.
- [x] Write `dashboard/snapshots/mart_choke_profile.parquet`.
- [x] Normalize Snowflake uppercase columns to dashboard lowercase contract.
- [x] Add export tests for the new snapshot.
- [x] Update GitHub Actions weekly profile so it exports and commits the choke snapshot after dbt passes.
- [x] Keep daily refresh free of HLTV/choke requirements.

### Phase 5: Streamlit Choke/Clutch Profile Page

**Goal:** Build the user-facing analysis while making sample limits obvious.

- [x] Create `dashboard/pages/3_Choke_Clutch_Profile.py`.
- [x] Page controls:
  - minimum maps slider, default `20`,
  - sample quality filter: `limited`, `directional`, `stable`,
  - team search/multiselect,
  - metric selector: lead-blown, halftime comeback, overtime, close maps.
- [x] KPI cards:
  - maps analyzed,
  - rounds analyzed,
  - lead-blown rate,
  - halftime comeback rate,
  - overtime win rate,
  - close-map win rate.
- [x] Main table:
  - team name,
  - world ranking,
  - sample quality,
  - maps analyzed,
  - largest lead,
  - leads blown,
  - lead-blown rate,
  - halftime leads lost,
  - comebacks,
  - overtime record,
  - close-map record.
- [x] Visuals:
  - bar chart for lead-blown rate among teams meeting minimum sample,
  - scatter plot of comeback rate vs lead-blown rate,
  - optional league-average reference lines.
- [x] Small-sample UX:
  - show a clear warning when most teams are `limited`,
  - de-emphasize or hide unstable rates by default,
  - never claim clutch/bracket metrics exist.
- [x] Add explanatory copy:
  - source: `hltv_unofficial`,
  - metrics are map/team pressure metrics, not player clutch metrics,
  - sample is still growing toward the 5k-map target.
- [x] Add tests:
  - page imports with sample snapshot,
  - small sample warning renders,
  - minimum map filter works,
  - raw IDs are not shown when team names exist.

### Phase 6: Data Growth Loop

**Goal:** Continue collecting data after the feature exists without changing code.

- [x] Keep fetching HLTV mapstats in 100-300 ID chunks.
- [x] Upload each chunk with a unique `--batch-id`.
- [x] Run weekly refresh after each meaningful batch.
- [x] Track progress toward:
  - 1k valid maps for acceptable v1 demo,
  - 2k valid maps for better team profiles,
  - 5k valid maps for stable tier-1 comparisons.
- [x] Keep dashboard labels honest until enough teams reach `stable`.

### Phase 7: Release Gate

- [x] `uv run ruff check .` passes.
- [x] `uv run pytest` passes.
- [x] `uv run dbt parse --project-dir dbt_project --profiles-dir dbt_project --no-partial-parse` passes.
- [x] `uv run dbt run --select +mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project` passes against Snowflake.
- [x] `uv run dbt test --select +mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project` passes against Snowflake.
- [x] `uv run python -m dashboard.export_snapshots` exports `mart_choke_profile` from Snowflake.
- [x] Streamlit dashboard page renders locally and in browser smoke tests.
- [x] Commit implementation as `feat(choke-profile): add team pressure dashboard`.

## Completed Workstream 2: CS API Bootstrap Profiles

**Goal:** Make `bootstrap_csapi.py` safe to run frequently by supporting explicit daily and weekly profiles with bounded API volume, clear logs, and environment overrides.

**Files:**
- Modify: `scripts/bootstrap_csapi.py`
- Modify: `airflow/dags/cs2_daily_matches.py` if daily orchestration exists
- Modify: `airflow/dags/cs2_weekly_rankings.py` if weekly orchestration exists
- Modify: `airflow/dags/cs2_dbt_run.py` if copy/dbt tasks need profile-specific raw tables
- Modify: `airflow/Dockerfile`
- Modify: `airflow/docker-compose.yml`
- Create: `README.md`
- Test: `tests/test_bootstrap_csapi.py` or nearest existing script test module
- Test: `tests/test_dags/test_airflow_runtime_packaging.py`

- [x] Add CLI flags: `--profile daily`, `--profile weekly`, and `--profile backfill`.
- [x] Keep all profile defaults overrideable through environment variables.
- [x] Daily profile default:
  - ingest current team rankings,
  - refresh current player profile snapshots,
  - ingest recent matches and player stats with a small page cap,
  - run in less than one Snowflake credit cycle when followed by targeted dbt models.
- [x] Weekly profile default:
  - ingest a deeper match window,
  - refresh rankings and player snapshots,
  - collect enough recent player stats for Hidden Gem rolling windows,
  - support continuation without duplicating existing S3 objects.
- [x] Backfill profile default:
  - explicit opt-in only,
  - larger page caps,
  - resumable chunk logging,
  - no scheduled Airflow trigger by default.
- [x] Skip existing raw S3 output objects before API calls so scheduled reruns and resumed chunks do not overwrite raw data.
- [x] Add profile summary logging before ingestion starts.
- [x] Add unit tests that each profile maps to the expected page limits and ingestion calls.
- [x] Wire Airflow schedules so daily and weekly runs call the matching profile.
- [x] Document recommended manual commands in `README.md` or setup docs.
- [x] Verify with targeted pytest and `uv run ruff check .`.
- [x] Commit as `feat(csapi): add bootstrap profiles`.

## Mostly Completed Workstream 3: Product Dashboard

**Goal:** Build a public dashboard that presents v1 features without re-querying Snowflake on every page refresh. Home, Upset Tracker, Hidden Gem Scout, and Choke/Clutch Profile are implemented.

**Files:**
- Create: `dashboard/Home.py`
- Create: `dashboard/pages/1_Upset_Tracker.py`
- Create: `dashboard/pages/2_Hidden_Gem_Scout.py`
- Create: `dashboard/pages/3_Choke_Clutch_Profile.py`
- Create: `dashboard/lib/snowflake.py`
- Create: `dashboard/lib/ml.py`
- Create: `dashboard/export_snapshots.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Implementation note:** Build the dashboard against cached mart snapshots and versioned ML artifacts first. Use a separate snapshot/export command for Snowflake reads so page refreshes do not directly hit the warehouse.

- [x] Add Streamlit, Plotly, and dashboard-specific Snowflake dependencies.
- [x] Add a shared Snowflake query helper that reads credentials from Streamlit secrets locally and in cloud.
- [x] Add `st.cache_data` wrappers with TTL aligned to daily or weekly ingestion profile cadence.
- [x] Add a snapshot export command so dashboard page refreshes do not query Snowflake directly.
- [x] Home page:
  - show project status,
  - link to the implemented analytical products,
  - expose data freshness from the marts.
- [x] Upset Tracker page:
  - show matches ranked by upset probability,
  - show model threshold and current model card summary,
  - show SHAP feature breakdown per selected match,
  - label predictions as watchlist signals, not certainties.
- [x] Hidden Gem Scout page:
  - filter by tier, team, stat floor, and trend direction,
  - show current team, tier, ranking, prospect score, recent sample size, and benchmark-gap trend,
  - chart recent versus previous 90-day gap.
- [x] Choke/Clutch Profile page:
  - show team pressure cards,
  - compare each team to league average,
  - expose metric quality flags.
- [x] Add a smoke test or import test for every implemented dashboard page.
- [x] Run the app locally with `uv run streamlit run dashboard/Home.py`.
- [x] Verify desktop and mobile layouts with screenshots before deployment.
- [x] Deploy to Streamlit Community Cloud and add the URL to `README.md`: https://cs2-analytics.streamlit.app/
- [x] Add scheduled GitHub Actions dashboard refresh workflow.
- [x] Commit as `feat(dashboard): add product dashboard`.

## Release Gate

- [x] `uv run ruff check .` passes.
- [x] `uv run pytest` passes.
- [x] `uv run dbt run --project-dir dbt_project --profiles-dir dbt_project` passes against Snowflake.
- [x] `uv run dbt test --project-dir dbt_project --profiles-dir dbt_project` passes against Snowflake.
- [x] Dashboard smoke test passes.
- [x] Choke/Clutch Profile page renders from a representative `mart_choke_profile` snapshot with metric quality flags and sample-size context.
- [x] README has manual run commands for ingestion, dbt, ML training, and dashboard.
- [x] README includes the deployed Streamlit URL.
