# CS2-Era Hidden Gem Scout Implementation

## Active Plan - Sync Workstream 3 Future Work Checkboxes

- [x] Audit Workstream 3 dashboard checkboxes against current repo files, tests, and GitHub Actions evidence.
- [x] Update `.planning/FUTURE_WORK_PLAN.md` Workstream 3 checkboxes only where the exact requirement is proven.
- [x] Report remaining Workstream 3 items that are still not done.

Review: Workstream 3 now reflects that the Choke/Clutch dashboard page is no
longer deferred. The page exists, Home links it, snapshot export includes
`mart_choke_profile`, the weekly GitHub run exported a 249-row Choke snapshot,
and local browser smoke tests render all dashboard pages. The only Workstream 3
release-gate items left unchecked are the exact unscoped Snowflake commands
`uv run dbt run --project-dir dbt_project --profiles-dir dbt_project` and
`uv run dbt test --project-dir dbt_project --profiles-dir dbt_project`; current
evidence proves the targeted hosted-dashboard selector, not the full unscoped
warehouse run/test.

Verification:

- `CS2_DASHBOARD_BASE_URL=http://localhost:8502 uv run pytest tests/test_dashboard_browser.py -q` passed with 4 tests.
- `uv run pytest tests/test_dashboard_pages.py tests/test_dashboard_export.py tests/test_dashboard_helpers.py -q` passed with 29 tests.
- GitHub Actions run `25751114954` exported `mart_choke_profile` with 249 rows and passed targeted dashboard dbt run/test.

## Active Plan - Sync Workstream 1 Future Work Checkboxes

- [x] Update `.planning/FUTURE_WORK_PLAN.md` Workstream 1 checkboxes from verified GitHub/Snowflake/dashboard evidence.
- [x] Leave any item unchecked if the exact requirement is not proven by repo state or GitHub logs.
- [x] Report the remaining not-done items.

## Review - Workstream 1 Completion Audit

Result: Workstream 1 is functionally complete, but
`.planning/FUTURE_WORK_PLAN.md` still has stale unchecked boxes in Phase 3 and
Phase 7. GitHub Actions run `25751114954` on `main` completed successfully on
2026-05-12, loaded `raw_hltv_round_history`, ran `+mart_choke_profile`, passed
113 dbt tests, exported `mart_choke_profile` with 249 rows, retrained the model,
and committed refreshed artifacts to `origin/main` as `0a15c7b`. Local `main` is
behind `origin/main` by that artifact commit, and the local working tree also
contains the uncommitted GitHub Actions runtime optimization changes.

Fresh audit verification:

- `uv run pytest tests/test_bootstrap_hltv_round_history.py tests/test_hltv_round_history.py tests/test_marts/test_choke_profile_sql.py tests/test_dashboard_export.py tests/test_dashboard_pages.py tests/test_github_actions_workflows.py -q` passed with 53 tests.
- `uv run ruff check .` passed.
- `SNOWFLAKE_ACCOUNT=dummy SNOWFLAKE_USER=dummy SNOWFLAKE_PRIVATE_KEY_PATH=/tmp/dummy_snowflake_key.p8 SNOWFLAKE_WAREHOUSE=dummy SNOWFLAKE_DATABASE=CS2_ANALYTICS uv run dbt parse --project-dir dbt_project --profiles-dir dbt_project --no-partial-parse` passed with existing accepted-values deprecation warnings.
- `gh run view 25751114954 --log` shows Snowflake dbt run/test and snapshot export passed for `mart_choke_profile`.
- `origin/main:dashboard/snapshots/mart_choke_profile.parquet` contains 249 rows: 202 `limited`, 44 `directional`, and 3 `stable`.

## Active Plan - GitHub Actions Daily/Weekly Split

Goal: make hosted dashboard refresh ownership explicit so scheduled GitHub
Actions have minimal overlap and do not create duplicate CS API raw loads.

- [x] Add regression tests for the workflow contract.
  - [x] Daily schedule should avoid Monday because weekly owns the Monday refresh.
  - [x] Weekly refresh should not call the deep CS API `weekly` profile.
  - [x] Weekly refresh should still load HLTV/choke-only raw data and export Choke snapshots.
- [x] Update `.github/workflows/dashboard-refresh.yml`.
  - [x] Daily schedule: current CS API, Valve regions, dbt/test/export for Upset Tracker and Hidden Gem Scout.
  - [x] Weekly schedule: Monday replacement refresh with bounded CS API `daily` profile, weekly HLTV load, dbt/test/export including Choke Profile, and ML retraining.
  - [x] Keep the deep CS API `weekly` profile as a manual/backfill path, not a scheduled dashboard action.
  - [x] Load only the current raw S3 date partition into Snowflake instead of scanning full source prefixes every run.
- [x] Update README operations docs so daily and weekly action responsibilities are clear.
- [x] Record the correction in `tasks/lessons.md`.
- [x] Verify focused workflow tests, YAML parse, and lint.

Review: GitHub Actions now has explicit schedule ownership. The daily hosted
refresh runs only Sunday and Tuesday-Saturday, while Monday is owned by the
weekly refresh. Weekly refreshes no longer invoke the deep CS API `weekly`
profile; they use the bounded CS API `daily` window, add weekly-only
HLTV/choke/model work, and export all three dashboard marts. Snowflake raw
`COPY` now targets only the current S3 `year=/month=/day=` partition under each
active source prefix instead of scanning every historical object.

Verification:

- `uv run pytest tests/test_github_actions_workflows.py -q` passed with 13 tests.
- `uv run pytest tests/test_github_actions_workflows.py tests/test_snowflake_setup_sql.py -q` passed with 14 tests.
- `uv run ruff check tests/test_github_actions_workflows.py` passed.
- `uv run ruff check .` passed.
- `git diff --check` passed.
- YAML parse smoke check for `.github/workflows/dashboard-refresh.yml` passed.

## Active Plan - Workstream 1 Choke/Clutch Team Profile

- [x] Phase 1: Make HLTV round-history uploads batch-safe.
  - [x] Add tests for unique upload filenames, `--batch-id` naming, unsafe filename rejection, S3 skip-existing behavior, and invalid JSON tolerance.
  - [x] Add CLI batch controls and deterministic batch summaries.
  - [x] Preserve invalid/null placeholder skipping without blocking valid maps.
- [x] Phase 2: Harden `mart_choke_profile` for small samples.
  - [x] Add sample-size fields, sample-quality buckets, league-average deltas, and metric availability flags.
  - [x] Add dbt schema tests and SQL contract tests for the mart contract.
- [x] Phase 3: Verify current warehouse/sample state where credentials and data are available.
  - [x] Generate a local representative snapshot from the current cache; external S3/Snowflake load is blocked in this shell because AWS and Snowflake env vars are not set.
  - [x] Record JSON files fetched, valid maps parsed, skipped placeholders, round rows, and current stable/directional sample counts.
- [x] Phase 4: Export Choke Profile snapshots.
  - [x] Add `mart_choke_profile` to default dashboard snapshot exports.
  - [x] Add export/workflow tests so weekly refresh exports the choke snapshot while daily stays free of HLTV requirements.
- [x] Phase 5: Add the Streamlit Choke/Clutch Profile page.
  - [x] Build filters, KPI cards, table, charts, and small-sample messaging from cached `mart_choke_profile`.
  - [x] Add page import/filter/display regression tests.
- [x] Phase 6: Document the no-code data growth loop.
  - [x] Record recommended 100-300 mapstat chunking and unique `--batch-id` uploads.
  - [x] Keep dashboard labels honest until enough teams reach stable samples.
- [ ] Phase 7: Run release-gate verification.
  - [x] Run focused tests during implementation.
  - [x] Run `uv run ruff check .`, `uv run pytest`, `uv run dbt parse --project-dir dbt_project --profiles-dir dbt_project --no-partial-parse`, snapshot load checks, and available Streamlit smoke checks.
  - [ ] Run live S3 upload, Snowflake `dbt run/test`, and Snowflake-backed `dashboard.export_snapshots` when AWS/Snowflake credentials are available.

Workstream 1 current local sample stats on 2026-05-12:

- JSON files scanned: 1,710
- Valid maps parsed: 1,466
- Skipped invalid/empty placeholder files: 244
- Round rows parsed into the representative snapshot: 30,962
- Teams profiled: 245
- Teams with at least 20 maps (`directional` or `stable`): 40
- Teams with at least 50 maps (`stable`): 3
- Representative snapshot: `dashboard/snapshots/mart_choke_profile.parquet`
- External load status: AWS/Snowflake environment variables are absent in this shell, so S3 upload and Snowflake `dbt run/test` remain CI/manual verification steps.

Review: Workstream 1 now has batch-safe HLTV raw uploads, a sample-aware
`mart_choke_profile` contract, default snapshot export support, a weekly-only
GitHub Actions Choke export path, a cached `mart_choke_profile` snapshot, and a
Streamlit Choke/Clutch Profile page linked from Home. The page defaults to a
20-map floor, filters by sample quality and team, shows pressure KPIs, displays
lead-blown and comeback visuals, and warns when most teams are still limited.

Verification:

- `uv run pytest tests/test_bootstrap_hltv_round_history.py tests/test_hltv_round_history.py -q` passed with 14 tests.
- `uv run pytest tests/test_marts/test_choke_profile_sql.py -q` passed with 7 tests.
- `uv run pytest tests/test_dashboard_pages.py tests/test_dashboard_export.py tests/test_github_actions_workflows.py tests/test_dashboard_browser.py -q` passed with 29 tests and 4 skipped browser tests when no server env was set.
- `uv run ruff check .` passed.
- `uv run pytest` passed with 285 tests, 4 skipped browser tests, and 1 existing Airflow warning.
- `SNOWFLAKE_ACCOUNT=dummy SNOWFLAKE_USER=dummy SNOWFLAKE_PRIVATE_KEY_PATH=/tmp/dummy_snowflake_key.p8 SNOWFLAKE_WAREHOUSE=dummy SNOWFLAKE_DATABASE=CS2_ANALYTICS uv run dbt parse --project-dir dbt_project --profiles-dir dbt_project --no-partial-parse` passed with existing accepted-values deprecation warnings.
- Local snapshot load check passed for `mart_upset_features`, `mart_hidden_gems`, and `mart_choke_profile`.
- `CS2_DASHBOARD_BASE_URL=http://localhost:8501 uv run pytest tests/test_dashboard_browser.py -q` passed with 4 browser checks against the local Streamlit server.

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

- [x] Fix dbt unique failures after raw COPY loads.
  - [x] Inspect failed GitHub Action logs for dbt test failures.
  - [x] Add regression coverage that `fact_matches` deduplicates repeated raw match rows.
  - [x] Deduplicate `fact_matches` at `match_id`/`source`/`map_name` before surrogate-key generation.
  - [x] Run focused SQL tests, dbt parse, and lint.

Review: After the profile-aware raw load passed, dbt failed on duplicate
`match_sk` values in `fact_matches` and `mart_upset_features`. The fix ranks
raw match rows at the declared fact grain and keeps one row before generating
`match_sk`, making dashboard refreshes resilient to repeated or overlapping raw
S3 loads. Verification passed: focused workflow/setup/DAG/SQL pytest suite,
Ruff, and `dbt parse --no-partial-parse` with dummy Snowflake environment
values. The parse still reports existing accepted-values deprecation warnings.

- [x] Make HLTV raw table load weekly-only in dashboard refresh.
  - [x] Add regression coverage that daily refresh does not require optional HLTV round history.
  - [x] Pass the resolved refresh profile into the raw-load step.
  - [x] Add `raw_hltv_round_history` only for the weekly profile.
  - [x] Record the lesson about optional manual HLTV loads.

Review: The reported log still included Faceit/PandaScore from the older
`64d3aaa` run, but the HLTV failure is valid for daily: local/manual HLTV data
should not block daily Upset Tracker and Hidden Gem Scout snapshots. The
workflow now loads CS API and Valve raw tables every run, and adds HLTV round
history only when `profile=weekly`.

- [x] Fix dashboard refresh failure on unused RAW table privileges.
  - [x] Reproduce the regression locally with tests that require active-only GitHub Action loads.
  - [x] Remove Faceit, PandaScore, and Liquipedia from the GitHub Action raw-load loop.
  - [x] Add Snowflake setup grants for active CS API raw tables.
  - [x] Record the lesson about keeping CI raw loads active-source only.
  - [x] Run focused workflow, setup, DAG, lint, and YAML checks.

Review: The dashboard refresh failed in GitHub Actions because the workflow tried
to `COPY INTO RAW.raw_faceit_matches`, an unused legacy source that the
`TRANSFORMER` role cannot operate on. The Action now loads only active hosted
dashboard sources: CS API matches/team rankings/player stats, Valve team
regions, and HLTV round history. Airflow keeps its full optional raw loader.
Verification passed: `uv run pytest tests/test_github_actions_workflows.py
tests/test_snowflake_setup_sql.py tests/test_dags/test_dbt_run_dag.py` with 16
passed and 1 existing Airflow deprecation warning, `uv run ruff check
tests/test_github_actions_workflows.py tests/test_snowflake_setup_sql.py
tests/test_dags/test_dbt_run_dag.py`, and a workflow YAML parse smoke check.

- [x] Ensure GitHub Action and Airflow COPY every raw S3 Parquet source.
  - [x] Add regression coverage for the full raw table/stage prefix matrix in GitHub Actions.
  - [x] Add regression coverage for the same raw table/stage prefix matrix in Airflow.
  - [x] Expand the GitHub Action Snowflake raw load to all raw sources.
  - [x] Run focused workflow, DAG, lint, and YAML checks.
  - [x] Document verification results.

Review: Replaced the dashboard refresh workflow's single-source raw load with
one all-raw `COPY INTO` loop covering Faceit matches/players, PandaScore
matches/players, CS API matches/team rankings/player stats, Valve team regions,
HLTV round history, and Liquipedia teams. Added matching regression coverage for
GitHub Actions and Airflow so both paths must keep the same staged raw table
matrix. Verification passed: `uv run pytest
tests/test_github_actions_workflows.py tests/test_dags/test_dbt_run_dag.py`
with 15 passed and 1 existing Airflow deprecation warning, `uv run ruff check
tests/test_github_actions_workflows.py tests/test_dags/test_dbt_run_dag.py`,
and a YAML parse smoke check for `.github/workflows/dashboard-refresh.yml`.

- [x] Make dashboard GitHub Action self-contained for no-Airflow refresh.
  - [x] Add regression coverage that the Action loads CS API S3 Parquet into Snowflake RAW tables.
  - [x] Add GitHub Action CS API `COPY INTO` step before dbt runs.
  - [x] Run focused workflow tests and lint.
  - [x] Document verification results.

Review: Added a dashboard-refresh workflow step that loads `raw_csapi_matches`,
`raw_csapi_team_rankings`, and `raw_csapi_player_stats` from the Snowflake S3
stage before dbt runs, so the GitHub Action no longer depends on optional
Airflow for the CS API S3-to-RAW hop. Verification passed:
`uv run pytest tests/test_github_actions_workflows.py`, `uv run ruff check
tests/test_github_actions_workflows.py`, and a YAML parse smoke check for
`.github/workflows/dashboard-refresh.yml`.

- [x] Remove series-inapplicable map controls from Upset Tracker dashboard.
  - [x] Add regression tests for hiding `map_name` from the table and filters.
  - [x] Remove `map_name` from the display columns and filter controls.
  - [x] Run focused dashboard tests and lint.

- [x] Investigate why Upset Tracker `map_name` values are all null.
  - [x] Trace `map_name` from raw CS API match ingestion through dbt marts.
  - [x] Check whether dashboard snapshots preserve or drop the field.
  - [x] Identify root cause and recommend the smallest fix.

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
  - [x] Terraform infrastructure.
  - [x] Great Expectations data quality.
  - [x] MLflow experiment tracking.
  - [x] Metabase or Superset plus dbt Semantic Layer.
  - [x] Discord bot integration.
  - [x] Upset Tracker and Hidden Gem model upgrades.
- [x] Remove streaming/Kafka scope from `.planning/V2_PLAN.md` after product clarification.

## Review

- Removed the series-inapplicable `map_name` column and Maps multiselect from
  the Upset Tracker Streamlit page. The page now exposes three filters:
  Regions, Ranking delta floor, and Outcome label. Added dashboard regression
  tests that prove `map_name` stays out of the display table and the Maps
  selector is not rendered. Verification: `uv run pytest
  tests/test_dashboard_pages.py` passed with 11 tests, and `uv run ruff check
  dashboard/pages/1_Upset_Tracker.py tests/test_dashboard_pages.py` passed.

- Upset Tracker `map_name` values are all null because CS API match ingestion
  currently emits one series-level record per match and hardcodes
  `map_name = None` in `CSAPIMatch.to_match_record()`. The live CS API
  `/matches/` payload does include a `maps` array with map names and scores,
  but the parser intentionally drops it. dbt preserves `m.map_name` through
  `fact_matches` and `mart_upset_features`, so the dashboard snapshot is
  reflecting upstream nulls rather than losing the column during export/load.

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

## Dashboard Logic and Visual Polish - 2026-05-11

- [x] Add tests that dashboard tables prefer team/player names over raw IDs.
- [x] Add tests that CS API ranking rows do not hard-code every team region as Global.
- [x] Add tests that Hidden Gem Scout sample-floor filtering follows the slider instead of the mart eligibility floor.
- [x] Enrich Upset Tracker and Hidden Gem marts/pages with readable team names and region handling.
- [x] Improve the Streamlit home page with data-rich metrics, charts, and cleaner navigation.
- [x] Verify targeted dashboard/dbt tests, lint, and local Streamlit runtime status.

## Review - Dashboard Logic and Visual Polish

- Root cause: CS API ranking records hard-coded `region = 'global'`, and the dashboard simply displayed that mart value. CS API `/rankings/` does not return a region field, so CS API records now keep region null and `dim_teams` enriches region from unique Liquipedia team-name matches when available.
- Added `team_a_name` and `team_b_name` to `mart_upset_features`; added `team_name` and `team_region` to `mart_hidden_gems`; dashboard tables now prefer names and hide raw provider IDs when names/display names are present.

## HLTV Choke Profile ID Join - 2026-05-12

- [x] Confirm cached HLTV map-stat payload includes numeric team IDs.
- [x] Update `mart_choke_profile` to join `dim_teams` by `team_id`.
- [x] Add contract coverage that prevents falling back to normalized team-name joins.
- [x] Verify parser, mart SQL contract, lint, full pytest, and dbt parse.

## Review - HLTV Choke Profile ID Join

- Confirmed `data/hltv_cache/map_stats/228493.json` carries `team1.id = 6248`
  and `team2.id = 7020`, which align with `dim_teams.team_id`.
- Updated the choke-profile mart to use `ta.team_id = t.team_id` for team
  metadata enrichment instead of fuzzy normalized-name matching.
- Verification: focused HLTV/mart tests passed with 8 tests; `uv run ruff
  check .` passed; `uv run pytest` passed with 262 tests, 3 skipped, and 1
  existing Airflow warning; `dbt parse --no-partial-parse` passed with dummy
  Snowflake env vars and existing `accepted_values` deprecation warnings.

## Valve Region Enrichment Plan - 2026-05-11

Goal: use Valve's public `counter-strike_regional_standings` repo only to fill missing team regions in Upset Tracker and related marts. Do not replace CS API match rankings or world-ranking features in this slice.

Architecture: add a small Valve standings ingestion path that discovers the latest `live/{year}` snapshot, parses regional standings markdown into raw records, stages those records in dbt, and lets `dim_teams` coalesce missing CS API regions from unique Valve team-name matches. Keep provider-ID-sensitive ranking features unchanged.

- [x] Confirm latest Valve snapshot discovery behavior.
  - [x] Test selecting the max numeric year under `live/`.
  - [x] Test selecting the latest date with all regional standings files available.
  - [x] Test parser handles Valve markdown tables and `<br />` formatting.

- [x] Add Valve region parser and model contract.
  - [x] Create a typed Valve standings model with `snapshot_date`, `team_name`, `normalized_team_name`, `region`, `regional_rank`, `global_rank`, `points`, `roster`, and `detail_path`.
  - [x] Parse regional standings files as the primary source of `region` and `regional_rank`.
  - [x] Parse global standings for `global_rank` only as context, not as a replacement for existing ranking features.
  - [x] Keep unknown or malformed rows out of the output with structured logging.

- [x] Add raw storage and warehouse staging.
  - [x] Add a Parquet schema for Valve standings records.
  - [x] Write records to the existing Hive-style `raw/valve/team_regions/year={yyyy}/month={mm}/day={dd}/data.parquet` path.
  - [x] Add Snowflake `RAW.raw_valve_team_regions` DDL and COPY support.
  - [x] Add `raw_valve_team_regions` to `sources.yml`.
  - [x] Add `stg_valve_team_regions` with one row per Valve team per snapshot.

- [x] Enrich team regions without changing rankings.
  - [x] Update `dim_teams` to coalesce CS API missing/`Global` regions from unique Valve normalized team-name matches.
  - [x] Prefer existing non-null Liquipedia regions over Valve.
  - [x] Do not change `world_ranking`, `ranking_source`, match-side rankings, or upset label logic.
  - [x] Add SQL regression tests that Valve fills null CS API regions while rankings remain CS API-backed.

- [x] Wire scheduled ingestion conservatively.
  - [x] Add Valve region refresh to the weekly rankings/profile path.
  - [x] Skip the S3 write when the same partition already exists.
  - [x] Log selected year/date and record count for observability.

- [x] Verify before marking done.
  - [x] Run targeted parser/model/dbt SQL tests.
  - [x] Run `uv run ruff check .`.
  - [x] Run `uv run pytest` or document any environment blocker.
  - [x] Run `dbt parse --no-partial-parse` with exported Snowflake env vars or document any environment blocker.
  - [ ] Export refreshed dashboard snapshot if warehouse access is available.

## Review - Valve Region Enrichment

- Added `cs2_analytics.ingestion.valve`, which discovers the newest complete Valve live snapshot, parses regional standings Markdown, attaches global-rank context, and writes region records to S3 with the existing Hive-style raw key convention.
- Added `RAW.raw_valve_team_regions`, `stg_valve_team_regions`, source metadata, Parquet schema, Snowflake COPY support, and `cs2_dbt_run` COPY wiring.
- Updated `dim_teams` so CS API teams with missing/`Global` region coalesce region from Liquipedia first, then the latest unique Valve normalized-name match. Rankings remain CS API-backed; Valve `global_rank` is staged for context but is not used as `world_ranking`.
- Wired the weekly rankings DAG to ingest Valve regions idempotently, skipping an already-written S3 key.
- Live smoke test on 2026-05-11 parsed 356 records from Valve snapshot `2026-05-04`; first parsed row was `FURIA`, `Americas`, regional rank 1, global rank 10.
- Verification passed: targeted pytest (`tests/test_valve_standings.py tests/test_modern_hidden_gems_sql.py tests/test_bootstrap_csapi.py`), `uv run ruff check .`, full `uv run pytest` (248 passed, 3 skipped, 1 existing Airflow warning), and `dbt parse --no-partial-parse` with dummy Snowflake env vars. `dbt parse` still reports the existing accepted-values deprecation warnings.
- Not run locally: Snowflake `dbt run/test` and dashboard snapshot export, because they require the live warehouse/raw table state after the new table is created and loaded.
- Removed the mart-level `recent_90_day_maps_played >= minimum_recent_90_day_maps` hard filter so Hidden Gem Scout can use the Streamlit sample-floor slider interactively.
- Reworked Home into a data-rich dashboard with KPI cards, match/prospect charts, region coverage, top prospect preview, page links, and snapshot freshness.
- Verification: targeted dashboard/source/SQL tests passed; `uv run ruff check .` passed; `dbt parse --no-partial-parse` passed with existing accepted-values deprecation warnings; full `uv run pytest -q` passed with 239 tests, 3 skipped, and 1 existing Airflow warning; browser smoke tests passed against `http://localhost:8501`.
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

## GitHub Actions Dashboard Refresh - 2026-05-11

- [x] Add a scheduled GitHub Actions workflow for daily and weekly dashboard refreshes.
- [x] Add manual `workflow_dispatch` profile selection for `daily` and `weekly`.
- [x] Materialize the Snowflake private key from GitHub Secrets without committing credentials.
- [x] Run CS API ingestion, dbt deps/run/test, weekly ML retraining, and snapshot export.
- [x] Commit changed dashboard snapshots and weekly ML artifacts back to the branch.
- [x] Document required GitHub repository secrets and manual run behavior in README.
- [x] Add tests that lock the workflow's required schedule and command contract.

## GitHub Actions Setup Docs - 2026-05-11

- [x] Add a setup section before daily operations in README.
- [x] Explain the post-PR merge GitHub Actions setup flow.
- [x] Clarify where to add repository secrets and how to run the first manual refresh.
- [x] Verify the docs-only change and commit it.

## v1 Plan Reality Refresh - 2026-05-11

- [x] Update `.planning/FUTURE_WORK_PLAN.md` so it reflects that CS API profiles, the implemented dashboard pages, browser checks, and dashboard refresh automation are complete.
- [x] Keep Choke/Clutch Profile as the remaining v1 product gap, with map-grain CS API ingestion and metric quality flags as the next implementation target.
- [x] Record deployed Streamlit Community Cloud URL: https://cs2-analytics.streamlit.app/

## HLTV Unofficial Choke Profile Source - 2026-05-11

- [x] Add tests for normalizing cached HLTV mapstats round history into team-level round winner rows.
- [x] Add a typed HLTV unofficial round-history raw schema and ingestion entrypoint that writes compact Parquet only.
- [x] Add Snowflake RAW DDL, dbt source, and staging model for `raw_hltv_round_history`.
- [x] Rebuild `mart_choke_profile` from exact round-history rows with honest unavailable flags for clutch/bracket data.
- [x] Add optional Node helper/docs for fetching HLTV mapstats slowly into local JSON cache without proxy rotation.
- [x] Verify targeted tests, dbt parse, ruff, and full pytest.

## Review - HLTV Unofficial Choke Profile Source

- Added `HLTVMatchMapStats` normalization for cached HLTV mapstats JSON, producing one compact `hltv_unofficial` row per round with side, team winner, score state, overtime flag, and source metadata.
- Added local/S3 bootstrap support through `scripts/bootstrap_hltv_round_history.py`; raw demo files are not used or stored.
- Added an optional `tools/fetch_hltv_mapstats.mjs` helper that fetches mapstats JSON slowly into `data/hltv_cache/`, which is gitignored. The helper requires local browser automation dependencies and skips already cached files.
- Added `raw_hltv_round_history`, `stg_hltv_round_history`, Airflow COPY support, and a round-history-backed `mart_choke_profile` with exact largest-lead, 5+ lead-blown, halftime collapse/comeback, overtime, and close-map metrics. Clutch and bracket data stay explicitly unavailable for v1.
- Important correction: this is still a backend data path plus first mart shape, not the finished Choke Profile analysis feature. The feature still needs a representative HLTV sample, Snowflake/dbt run/test on that sample, a dashboard snapshot, and a Streamlit page with metric quality and sample-size context.
- Verification: targeted pytest passed with 14 tests and 1 existing Airflow warning; `dbt parse --no-partial-parse` passed with existing accepted-values deprecation warnings; `uv run ruff check .` passed; `uv run pytest` passed with 260 tests, 3 skipped browser tests, and 1 existing Airflow warning.

## Choke Profile Feature Plan Refresh - 2026-05-12

- [x] Update `.planning/FUTURE_WORK_PLAN.md` with a detailed Choke Profile implementation plan.
- [x] Include batch-safe S3 upload work for HLTV round-history Parquet.
- [x] Include sample-quality fields, dashboard behavior, snapshot export, and release gates.

## Review - Choke Profile Feature Plan Refresh

- Choke Profile should be implemented now against the current small sample, while the data collection loop continues toward 5k valid maps.
- The plan now explicitly separates backend ingestion, batch upload safety, mart sample-quality contracts, Snowflake verification, snapshot export, Streamlit dashboard work, and the ongoing data-growth loop.
