# CS2-Era Hidden Gem Scout Implementation

- [x] Move Upset Tracker match lineage to CS API.
  - [x] Add regression tests for CS API match ingestion and upset-source filtering.
  - [x] Ingest CS API `/matches/` rows into `raw/csapi/matches/`.
  - [x] Add `raw_csapi_matches`, `stg_csapi_matches`, and Snowflake/Airflow COPY support.
  - [x] Include CS API matches in `int_matches_unioned`.
  - [x] Filter `mart_upset_features` to `source = 'csapi'` to avoid provider-ID mismatch.
  - [x] Verify targeted tests, dbt parse, ruff, and full pytest.

- [x] Remove historical Kaggle data from CS2 mart lineage.
  - [x] Add regression tests that Kaggle no longer feeds match/player unions or team rankings.
  - [x] Remove Kaggle from `int_matches_unioned` and `int_players_unioned`.
  - [x] Remove Kaggle-derived team IDs/rankings from `dim_teams`.
  - [x] Update accepted source tests for modern-only intermediate models.
  - [x] Verify targeted SQL tests and full pytest.

- [x] Remove Kaggle pipeline completely.
  - [x] Delete Kaggle bootstrap script, ingestion module, fixtures, and tests.
  - [x] Remove Kaggle raw/staging dbt models, sources, Snowflake DDL, and Airflow COPY statements.
  - [x] Remove Kaggle settings and dependency from project metadata/lockfile.
  - [x] Update docs and remaining source examples away from Kaggle.
  - [x] Verify no Kaggle implementation references remain outside negative regression tests.

- [x] Investigate Hidden Gem Scout player/team/ranking mismatch for player ID 11893.
  - [x] Reproduce source truth with live CS API: player 11893 is ZywOo on Vitality, and Vitality is rank 1.
  - [x] Trace player team assignment from CS API raw data into `dim_players`, `fact_player_stats`, and `mart_hidden_gems`.
  - [x] Trace team ranking/tier assignment from VRS rankings into `dim_teams` and Hidden Gem Scout marts.
  - [x] Add a regression test for stale or incorrect CS API player-team/ranking joins.
  - [x] Implement the smallest root-cause fix and rerun targeted verification.

- [x] Add CS API bootstrap progress logging and chunk controls after rate-limit/hang report.

- [x] Confirm product direction: use Valve VRS + PandaScore + CS API before HLTV scraping.
- [x] Add failing tests for CS API VRS ranking parsing.
- [x] Add failing tests for CS API player-stat parsing.
- [x] Add typed canonical/Parquet schemas for modern team rankings and player stats.
- [x] Implement CS API VRS ingestion into `raw/csapi/team_rankings/`.
- [x] Implement CS API match-driven player-stat ingestion into `raw/csapi/player_stats/`.
- [x] Add Snowflake raw tables and `COPY INTO` commands.
- [x] Add dbt sources/staging models for CS API.
- [x] Patch `dim_teams` to prefer Liquipedia, then CS API VRS, then Kaggle legacy rankings.
- [x] Patch `fact_player_stats`/player union so CS API can feed modern Hidden Gem Scout stats.
- [x] Patch `mart_player_leaderboard` to use four tiers.
- [x] Patch `mart_hidden_gems` to expose `prospect_score` and remove the tier-4 fallback.
- [ ] Run dbt run/test and Snowflake distribution checks after RAW tables are created by ACCOUNTADMIN.
- [ ] Update `.planning/REQUIREMENTS.md` and phase docs after verification.

## Commit Batching Plan

- [x] Inspect working tree and identify local-only files to exclude.
- [x] Commit safety ignores for secrets/local generated caches.
- [x] Commit optional Liquipedia/config/Airflow changes.
- [x] Commit Kaggle multi-table ingestion.
- [x] Commit CS API ranking/player-stat ingestion.
- [x] Commit dbt marts for upset tracker, hidden gems, and choke profile.
- [x] Commit ML upset tracker training, prediction, artifacts, and tests.
- [x] Commit Airflow import cleanup.
- [x] Commit project docs/planning/graph artifacts.
- [x] Push commits to GitHub.

## Design

Hidden Gem Scout and Upset Tracker remain SQL-first. Modern data should come from:

1. CS API's VRS ranking endpoint for team ranking/points from the CS2 era.
2. CS API match rows for ranking-compatible match outcomes.
3. CS API match/player stat endpoints for current player/team form.
4. PandaScore or FACEIT only behind explicit identity mapping, not as default mart joins.

## Active Plan

- [x] Tune Upset Tracker classification threshold for balanced upset predictions.
  - [x] Measure default `0.5` threshold confusion matrix and class recall.
  - [x] Add regression tests for validation-based threshold selection.
  - [x] Persist the selected threshold and recall-oriented metrics.
  - [x] Retrain model artifacts from Snowflake and verify tests/lint.

- [x] Complete Hidden Gem Scout benchmark-gap trend.
  - [x] Confirm player-level clutch rate is unavailable in current raw/fact schemas.
  - [x] Keep HG-02/HG-03 on available stats: rating, ADR, K/D, and KAST.
  - [x] Replace ADR-only trend with recent-vs-previous 90-day normalized gap to tier-above thresholds.
  - [x] Add 20 recent 90-day stat-row eligibility floor to remove one-off outliers.
  - [x] Update requirements and dbt metadata for gap trend outputs.

The dashboard-facing output stays `mart_hidden_gems`: one row per flagged
tier-2/3/4 prospect, with tier-above thresholds, trend direction, and a numeric
`prospect_score` for sorting.

## Future Work Plan

- [x] Create `.planning/FUTURE_WORK_PLAN.md` for the remaining v1 work:
  - [x] Choke/Clutch team profile.
  - [x] CS API daily, weekly, and backfill bootstrap profiles.
  - [x] Streamlit dashboard for every product feature.
- [x] Create `.planning/V2_PLAN.md` for platform expansion:
  - [x] Kafka streaming and real-time dashboard updates.
  - [x] Terraform infrastructure.
  - [x] Great Expectations data quality.
  - [x] MLflow experiment tracking.
  - [x] Metabase or Superset plus dbt Semantic Layer.
  - [x] Discord bot integration.
  - [x] Upset Tracker and Hidden Gem model upgrades.

## Review

- Fixed Hidden Gem Scout current-team correctness by ingesting CS API `/players/stats/raw`
  rows as current player profile snapshots with `match_id = null`, so they update
  `dim_players` without becoming fake match facts.
- Updated `mart_hidden_gems` and `mart_player_leaderboard` to tier/rank players by
  `dim_players` current team first, falling back to the historical match team only
  when no current profile exists.
- Updated `int_players_unioned` so CS API current profile snapshots survive
  profile-level deduplication ahead of older provider profile rows.
- Verified live CS API on 2026-05-11: player `11893` is `zywoo`, team `9565`
  Vitality; CS API rankings have Vitality rank 1.
- Verification: `uv run ruff check .` passed; `uv run pytest` passed with
  230 tests and 1 existing Airflow warning. `uv run dbt parse --project-dir
  dbt_project --profiles-dir dbt_project` is blocked locally by missing
  `SNOWFLAKE_ACCOUNT`. `uv run mypy .` still fails on existing broad DAG/test
  typing issues and third-party stub gaps unrelated to this change.
- Removed historical Kaggle rows from modern mart lineage because Kaggle team IDs
  can be team-name strings while CS API player/team IDs are numeric HLTV-style
  IDs. `int_matches_unioned`, `int_players_unioned`, and `dim_teams` now exclude
  Kaggle, while raw/staging Kaggle loaders remain available for archival use.
- Verification after Kaggle removal: `uv run ruff check .` passed; `uv run
  pytest` passed with 231 tests and 1 existing Airflow warning; `dbt parse`
  passed with dummy Snowflake env vars and only existing accepted_values
  deprecation warnings.
- Removed the Kaggle pipeline entirely: bootstrap script, ingestion client,
  dbt raw/staging definitions, Snowflake setup tables/COPY statements, Airflow
  COPY statements, pytest fixtures/tests, config fields, dependency, and docs.
  The only remaining Kaggle text is in negative regression tests that assert the
  removed source does not re-enter modern marts. Verification: targeted pytest
  passed with 36 tests; `uv run ruff check .` passed; `uv run pytest` passed
  with 190 tests and 1 existing Airflow warning; `dbt parse --no-partial-parse`
  passed with dummy Snowflake env vars and existing accepted_values deprecation
  warnings.
- Moved Upset Tracker to CS API match lineage. `bootstrap_csapi.py` now writes
  CS API series-level match rows to `raw/csapi/matches/`; dbt exposes
  `stg_csapi_matches`, includes CS API in `int_matches_unioned`, and filters
  `mart_upset_features` to `source = 'csapi'` so match team IDs align with CS API
  rankings. Verification: `uv run pytest tests/test_csapi_client.py
  tests/test_modern_hidden_gems_sql.py` passed with 19 tests; `uv run ruff
  check .` passed; `uv run pytest` passed with 194 tests and 1 existing Airflow
  warning; `dbt parse --no-partial-parse` passed with dummy Snowflake env vars
  and existing accepted_values deprecation warnings.
- Fixed ML training against CS API/Snowflake upset features where nullable
  boolean flags could crash `.astype(int)`. Verification: regression pytest
  passed, `uv run pytest tests/test_ml` passed with 5 tests, `uv run ruff check
  .` passed, and `set -a; source .env; set +a; uv run python -m ml.train`
  exited successfully.
- Converted Upset Tracker training from a completed-match classifier into a
  pre-match predictor by removing final-score leakage columns from the shared
  ML feature contract. The model now uses `ranking_delta`, `is_cross_region`,
  `team_a_ranking`, and `team_b_ranking`; retraining on the CS API-backed mart
  produced holdout ROC-AUC `0.7275` instead of the leaked `1.0000`.
- Tuned Upset Tracker's binary cutoff for upset recall. The raw model still
  ranks with ROC-AUC around `0.7258`, but the saved F2 decision threshold
  `0.2168` raises holdout upset recall to `0.9739` with precision `0.3200`, so
  predictions should be treated as a watchlist rather than a certainty score.
- Retuned Upset Tracker away from the recall-heavy threshold because it
  predicted too many upsets. The saved F0.75 threshold `0.3841` caps validation
  alert rate at the validation upset base rate; on the newest holdout it predicts
  upsets for `0.2604` of matches versus an actual `0.2516`, with precision
  `0.4370` and recall `0.4522`.
- Completed Hidden Gem HG-04 as a true benchmark-gap trend. `mart_hidden_gems`
  now compares recent and previous 90-day averages for ADR, K/D, KAST, and
  rating against the tier-above thresholds, emitting `gap_growing`,
  `gap_shrinking`, `gap_flat`, or `insufficient_history`. Player-level clutch
  rate remains explicitly skipped because the current fact tables do not contain
  clutch-event data.
- Added a 20-row recent 90-day sample-size floor to Hidden Gem Scout. The mart
  now exposes `recent_90_day_maps_played`, `minimum_recent_90_day_maps`, and
  `meets_recent_sample_size` so the dashboard can explain eligibility.

- Reworked CS API player stats to use `/matches/` plus `/matches/{matchid}/stats`
  so each row has a real match ID and match date.
- Verified targeted pytest, ruff, mypy, and the full pytest suite.
- Blocked on live dbt run/test until the two new RAW tables are created in
  Snowflake by a role with ownership/DDL privileges on `CS2_ANALYTICS.RAW`.

## Graphify Refresh - 2026-05-11

- [x] Rebuild the knowledge graph for the repository with graphify, excluding dot-prefixed directories.
- [x] Review generated graph outputs for a non-empty graph and report sections.

## Review

- Rebuilt `graphify-out/graph.json`, `graphify-out/graph.html`,
  `graphify-out/GRAPH_REPORT.md`, `graphify-out/manifest.json`, and
  `graphify-out/cost.json` from the current codebase.
- Verified the graph is non-empty with 1,280 nodes, 1,718 edges, and 163
  communities.
- Verified no graph node source paths live under dot-prefixed directories.
- Token benchmark estimates ~36.8x fewer tokens per query than reading the
  corpus directly.

## v1 Future Work Continuation - 2026-05-11

- [x] Dispatch independent agents for pressure-source research, CS API bootstrap profiles, and dashboard input mapping.
- [x] Integrate CS API daily, weekly, and backfill bootstrap profiles with tests and Airflow wiring.
- [x] Convert pressure-source research into the next safe Choke/Clutch implementation step.
- [x] Convert dashboard input mapping into a scoped Streamlit dashboard implementation step.
- [x] Run targeted tests for changed files, then `uv run ruff check .`.
- [x] Update `.planning/FUTURE_WORK_PLAN.md` and this review section with what shipped and what remains.

## Review - v1 Future Work Continuation

- Started from `.planning/FUTURE_WORK_PLAN.md`.
- Checked `tasks/lessons.md` before implementation; key constraints are to keep provider IDs aligned, avoid invented clutch metrics, and keep long CS API bootstraps visibly bounded.
- Added CS API bootstrap profiles:
  - `daily`: bounded recent match/player-stat refresh plus rankings and current player profiles.
  - `weekly`: deeper rolling-window refresh for Hidden Gem Scout.
  - `backfill`: explicit opt-in only with larger resumable chunks.
- Added per-output S3 existence checks so scheduled profile reruns skip already-written raw objects instead of overwriting same-day data.
- Wired Airflow daily and weekly DAGs to run the matching CS API profile and updated the Airflow Docker image/compose mounts so `scripts.bootstrap_csapi` is importable in-container.
- Added `README.md` run commands for CS API profiles, dbt refreshes, ML training, and Airflow startup.
- Pressure-source research result: next Choke/Clutch implementation should add CS API map-grain ingestion for exact map overtime W/L; lead-blown, halftime comeback, bracket, and elimination metrics remain proxy/unavailable until round or bracket data exists with an identity map.
- Dashboard research result: first Streamlit slice should read cached mart snapshot Parquet files plus versioned ML artifacts, not query Snowflake on every page refresh.
- Verification: `uv run pytest tests/test_bootstrap_csapi.py tests/test_dags/test_airflow_runtime_packaging.py tests/test_dags/test_daily_matches.py tests/test_dags/test_dag_structure.py tests/test_dags/test_dbt_run_dag.py` passed with 31 tests and 1 existing Airflow deprecation warning.
- Verification: `uv run ruff check .` passed.
- Verification: `uv run pytest` passed with 214 tests and 1 existing Airflow deprecation warning.

## Dashboard Workstream 3 - 2026-05-11

- [x] Build the Streamlit dashboard slice from `.planning/FUTURE_WORK_PLAN.md` while leaving `dashboard/pages/3_Choke_Clutch_Profile.py` out until that product is implemented.
- [x] Add dashboard dependencies and shared cached data/model helpers.
- [x] Add Home, Upset Tracker, and Hidden Gem Scout pages backed by cached mart snapshots and versioned ML artifacts.
- [x] Add smoke/import tests for the implemented dashboard pages and helper modules.
- [x] Update README dashboard commands and note that Choke/Clutch is intentionally deferred.
- [x] Verify with targeted dashboard tests.
- [x] Verify with `uv run ruff check .`.
- [x] Attempt `uv run streamlit run dashboard/Home.py` locally or document any environment blocker.

## Review - Dashboard Workstream 3

- Added a Streamlit dashboard shell with Home, Upset Tracker, and Hidden Gem Scout pages. Choke/Clutch remains intentionally absent until Workstream 1 is implemented.
- Added cached Parquet snapshot helpers, Snowflake export/query helpers, model-card/threshold helpers, batch Upset Tracker scoring, and selected-row SHAP explanations.
- Added `dashboard.export_snapshots` so Snowflake reads happen in an explicit snapshot export step instead of on every page refresh.
- Added `streamlit` and `plotly` dependencies and refreshed `uv.lock`.
- Updated README dashboard commands for snapshot export and local app startup.
- Verification: `uv run pytest tests/test_dashboard_helpers.py tests/test_dashboard_pages.py tests/test_dashboard_export.py` passed with 14 tests.
- Verification: `uv run streamlit run dashboard/Home.py --server.headless true --server.port 8505 --browser.gatherUsageStats false` started successfully, and `curl -fsS http://localhost:8505/_stcore/health` returned `ok`.
- Verification: `uv run ruff check .` passed.
- Verification: `uv run pytest` passed with 228 tests and 1 existing Airflow deprecation warning.

## Dashboard Browser Debug - 2026-05-11

- [x] Reproduce dashboard page failures in a real browser with Playwright against localhost.
- [x] Fix Snowflake snapshot column normalization so uppercase Parquet exports satisfy lowercase dashboard/ML contracts.
- [x] Fix Streamlit slider bounds for empty or missing numeric filter columns.
- [x] Fix Upset Tracker match selector labels when match IDs contain null values.
- [x] Add opt-in Playwright browser smoke tests gated by `CS2_DASHBOARD_BASE_URL`.
- [x] Verify desktop and mobile screenshots for implemented dashboard pages.
- [x] Verify with targeted dashboard tests, browser smoke tests, `uv run ruff check .`, and `uv run pytest`.

## Review - Dashboard Browser Debug

- Root cause: exported Snowflake snapshots had uppercase column names, while the dashboard pages and ML scoring expected lowercase mart columns. That made filters look empty, hid real metrics, and raised missing-feature errors.
- Secondary root cause: Streamlit sliders were created with `min_value=0` and computed `max_value=0` when page data appeared empty.
- Added `playwright` as a dev dependency and installed Chromium for local browser checks.
- Verification: `CS2_DASHBOARD_BASE_URL=http://localhost:8505 uv run pytest tests/test_dashboard_browser.py -q` passed with 3 browser checks.
- Verification: `uv run pytest` passed with 232 tests, 3 skipped opt-in browser tests, and 1 existing Airflow deprecation warning.
